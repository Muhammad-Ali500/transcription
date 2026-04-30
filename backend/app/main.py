import os
import time
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.websocket.manager import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    await init_db()
    logger.info("Application startup complete")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="Transcription & Segmentation API",
    description="Production-scale audio transcription and segmentation service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "upload", "description": "File upload operations"},
        {"name": "transcription", "description": "Transcription operations"},
        {"name": "segmentation", "description": "Segmentation operations"},
        {"name": "jobs", "description": "Job management and monitoring"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://transcript.dev-in.com", "http://transcript.dev-in.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    request_id = str(uuid.uuid4())
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 4))
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": app.version, "timestamp": time.time()}


@app.get("/health/ready")
async def readiness_check():
    return {"status": "ready"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_client_message(websocket, data)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


from app.api.upload import router as upload_router
from app.api.transcription import router as transcription_router
from app.api.segmentation import router as segmentation_router
from app.api.jobs import router as jobs_router

app.include_router(upload_router, prefix=settings.API_PREFIX)
app.include_router(transcription_router, prefix=settings.API_PREFIX)
app.include_router(segmentation_router, prefix=settings.API_PREFIX)
app.include_router(jobs_router, prefix=settings.API_PREFIX)
