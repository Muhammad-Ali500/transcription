import json
import logging
import asyncio
from typing import Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, set] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, connection_id: str = None):
        await websocket.accept()
        if connection_id is None:
            connection_id = str(id(websocket))
        async with self._lock:
            self.active_connections[connection_id] = websocket
            self.subscriptions[connection_id] = set()
        logger.info(f"WebSocket connected: {connection_id}")
        await self.send_personal_message(
            {"type": "connected", "connection_id": connection_id, "message": "Connected to real-time updates"},
            websocket,
        )

    async def disconnect(self, websocket: WebSocket):
        conn_id = None
        async with self._lock:
            for cid, ws in self.active_connections.items():
                if ws == websocket:
                    conn_id = cid
                    break
            if conn_id:
                del self.active_connections[conn_id]
                self.subscriptions.pop(conn_id, None)
        if conn_id:
            logger.info(f"WebSocket disconnected: {conn_id}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")

    async def broadcast(self, message: dict, exclude: WebSocket = None):
        async with self._lock:
            connections = list(self.active_connections.values())
        dead_connections = []
        for ws in connections:
            if ws == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)
        for ws in dead_connections:
            await self.disconnect(ws)

    async def send_job_update(self, job_id: str, data: dict):
        message = {"type": "job_update", "job_id": str(job_id), "data": data}
        await self.broadcast(message)

    async def send_job_complete(self, job_id: str, data: dict):
        message = {"type": "job_complete", "job_id": str(job_id), "data": data}
        await self.broadcast(message)

    async def send_job_error(self, job_id: str, error: str):
        message = {"type": "job_error", "job_id": str(job_id), "data": {"error": error}}
        await self.broadcast(message)

    async def handle_client_message(self, websocket: WebSocket, data: dict):
        msg_type = data.get("type", "")
        conn_id = None
        async with self._lock:
            for cid, ws in self.active_connections.items():
                if ws == websocket:
                    conn_id = cid
                    break

        if msg_type == "subscribe":
            job_id = data.get("job_id")
            if conn_id and job_id:
                self.subscriptions[conn_id].add(job_id)
                await self.send_personal_message({"type": "subscribed", "job_id": job_id}, websocket)

        elif msg_type == "unsubscribe":
            job_id = data.get("job_id")
            if conn_id and job_id:
                self.subscriptions[conn_id].discard(job_id)
                await self.send_personal_message({"type": "unsubscribed", "job_id": job_id}, websocket)

        elif msg_type == "ping":
            await self.send_personal_message({"type": "pong"}, websocket)


manager = ConnectionManager()
