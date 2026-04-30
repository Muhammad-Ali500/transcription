import os
import json
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import Response

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import Job, TranscriptionResult
from app.services.transcription_service import get_transcription_service
from app.services.minio_service import get_minio_service
from app.tasks.transcription_tasks import transcribe_audio_task
from app.tasks.segmentation_tasks import segment_transcription_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcription", tags=["transcription"])


@router.post("/", status_code=201)
async def create_transcription(
    file: UploadFile = File(...),
    language: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    from app.api.upload import validate_file_extension, detect_content_type
    from app.config import settings

    if not file.filename or not validate_file_extension(file.filename):
        raise HTTPException(status_code=400, detail=f"File type not supported. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}")

    content = await file.read()
    file_size = len(content)
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds maximum")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{file_id}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    minio_service = get_minio_service()
    minio_object_name = f"{unique_filename}"
    minio_service.upload_file(file_path, minio_object_name, detect_content_type(file.filename))

    job = Job(
        id=uuid.uuid4(),
        status="pending",
        job_type="transcription",
        filename=file.filename,
        file_path=minio_object_name,
        file_size=file_size,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task = transcribe_audio_task.delay(
        job_id=str(job.id),
        file_path=minio_object_name,
        source="minio",
        language=language,
    )
    job.celery_task_id = task.id
    await db.commit()

    return {
        "id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "filename": job.filename,
        "file_size": job.file_size,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.get("/{job_id}")
async def get_transcription(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.job_type != "transcription":
        raise HTTPException(status_code=409, detail="Job is not a transcription job")

    transcription = await db.execute(
        select(TranscriptionResult).where(TranscriptionResult.job_id == job_id)
    )
    transcription_result = transcription.scalar_one_or_none()

    if job.status == "completed" and transcription_result:
        return {
            "id": transcription_result.id,
            "job_id": transcription_result.job_id,
            "text": transcription_result.text,
            "language": transcription_result.language,
            "duration": transcription_result.duration,
            "segments": transcription_result.segments,
            "created_at": transcription_result.created_at,
        }

    if job.status == "processing":
        return {"job_id": job_id, "status": "processing", "message": "Transcription in progress"}

    if job.status == "failed":
        raise HTTPException(status_code=500, detail=job.error_message or "Transcription failed")

    return {"job_id": job_id, "status": "pending", "message": "Job is queued"}


@router.get("/{job_id}/download")
async def download_transcription(
    job_id: str,
    format: str = Query(default="text"),
    db: AsyncSession = Depends(get_db),
):
    transcription = await db.execute(
        select(TranscriptionResult).where(TranscriptionResult.job_id == job_id)
    )
    result = transcription.scalar_one_or_none()
    if not result:
        raise HTTPException(status_code=404, detail="Transcription not found")

    if format == "srt":
        content = _format_as_srt(result)
        media_type = "text/plain"
        filename = f"transcription_{job_id}.srt"
    elif format == "vtt":
        content = _format_as_vtt(result)
        media_type = "text/vtt"
        filename = f"transcription_{job_id}.vtt"
    elif format == "json":
        content = json.dumps({
            "text": result.text,
            "language": result.language,
            "duration": result.duration,
            "segments": result.segments,
        }, indent=2)
        media_type = "application/json"
        filename = f"transcription_{job_id}.json"
    else:
        content = _format_as_text(result)
        media_type = "text/plain"
        filename = f"transcription_{job_id}.txt"

    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/{job_id}/segments")
async def get_transcription_segments(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    transcription = await db.execute(
        select(TranscriptionResult).where(TranscriptionResult.job_id == job_id)
    )
    result = transcription.scalar_one_or_none()
    if not result or not result.segments:
        return {"segments": [], "total": 0, "page": page, "page_size": page_size}

    all_segments = result.segments
    total = len(all_segments)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = all_segments[start:end]

    return {"segments": paginated, "total": total, "page": page, "page_size": page_size}


@router.post("/{job_id}/segment")
async def segment_transcription(
    job_id: str,
    method: str = "silence",
    db: AsyncSession = Depends(get_db),
):
    transcription = await db.execute(
        select(TranscriptionResult).where(TranscriptionResult.job_id == job_id)
    )
    result = transcription.scalar_one_or_none()
    if not result:
        raise HTTPException(status_code=404, detail="Transcription not found")

    new_job = Job(
        id=uuid.uuid4(),
        status="pending",
        job_type="segmentation",
        filename=f"segmentation_of_{job_id}",
        file_path="",
        file_size=0,
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    transcription_data = {
        "text": result.text,
        "language": result.language,
        "duration": result.duration,
        "segments": result.segments,
    }

    task = segment_transcription_task.delay(
        job_id=str(new_job.id),
        transcription_result=transcription_data,
        method=method,
    )
    new_job.celery_task_id = task.id
    await db.commit()

    return {
        "id": new_job.id,
        "status": new_job.status,
        "job_type": new_job.job_type,
        "filename": new_job.filename,
        "created_at": new_job.created_at,
        "updated_at": new_job.updated_at,
    }


def _format_as_srt(result) -> str:
    lines = []
    for i, seg in enumerate(result.segments or [], 1):
        start = _seconds_to_srt_time(seg.get("start", 0))
        end = _seconds_to_srt_time(seg.get("end", 0))
        lines.append(f"{i}\n{start} --> {end}\n{seg.get('text', '')}\n")
    return "\n".join(lines)


def _format_as_vtt(result) -> str:
    lines = ["WEBVTT\n"]
    for seg in result.segments or []:
        start = _seconds_to_srt_time(seg.get("start", 0))
        end = _seconds_to_srt_time(seg.get("end", 0))
        lines.append(f"{start} --> {end}\n{seg.get('text', '')}\n")
    return "\n".join(lines)


def _format_as_text(result) -> str:
    lines = []
    for seg in result.segments or []:
        start = _format_timestamp(seg.get("start", 0))
        lines.append(f"[{start}] {seg.get('text', '')}")
    return "\n".join(lines) if lines else result.text


def _seconds_to_srt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def _format_timestamp(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"
