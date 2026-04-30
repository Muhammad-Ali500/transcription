import os
import uuid
import logging
import mimetypes
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from app.database import get_db
from app.config import settings
from app.models.models import Job
from app.schemas.schemas import JobResponse, JobCreate, BatchUploadRequest
from app.services.minio_service import get_minio_service, MinioService
from app.tasks.transcription_tasks import transcribe_audio_task
from app.tasks.segmentation_tasks import process_full_pipeline_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


def validate_file_extension(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in settings.ALLOWED_EXTENSIONS


def detect_content_type(filename: str) -> str:
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"


@router.post("/direct", response_model=JobResponse)
async def upload_direct(
    file: UploadFile = File(...),
    job_type: str = Form(default="transcription"),
    language: Optional[str] = Form(default=None),
    do_segmentation: bool = Form(default=False),
    segmentation_method: str = Form(default="silence"),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{file_id}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    content_type = detect_content_type(file.filename)
    minio_service = get_minio_service()
    minio_object_name = f"{unique_filename}"
    minio_service.upload_file(file_path, minio_object_name, content_type)

    job = Job(
        id=uuid.uuid4(),
        status="pending",
        job_type=job_type,
        filename=file.filename,
        file_path=minio_object_name,
        file_size=file_size,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if do_segmentation:
        task = process_full_pipeline_task.delay(
            job_id=str(job.id),
            file_path=minio_object_name,
            source="minio",
            do_segmentation=True,
            segmentation_method=segmentation_method,
            language=language,
        )
    else:
        task = transcribe_audio_task.delay(
            job_id=str(job.id),
            file_path=minio_object_name,
            source="minio",
            language=language,
        )

    job.celery_task_id = task.id
    await db.commit()
    await db.refresh(job)

    logger.info(f"Created job {job.id} for file {file.filename}")
    return {
        "id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "filename": job.filename,
        "file_size": job.file_size,
        "file_path": job.file_path,
        "celery_task_id": job.celery_task_id,
        "error_message": job.error_message,
        "result": job.result,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "user_id": job.user_id,
    }


@router.post("/minio", response_model=JobResponse)
async def upload_from_minio(
    object_name: str = Body(..., embed=True),
    job_type: str = Body(default="transcription"),
    language: Optional[str] = Body(default=None),
    do_segmentation: bool = Body(default=False),
    segmentation_method: str = Body(default="silence"),
    db: AsyncSession = Depends(get_db),
):
    minio_service = get_minio_service()
    if not minio_service.file_exists(object_name):
        raise HTTPException(status_code=404, detail=f"File '{object_name}' not found in storage")

    file_info = minio_service.get_file_info(object_name)
    file_size = file_info.get("size", 0)
    filename = os.path.basename(object_name)

    job = Job(
        id=uuid.uuid4(),
        status="pending",
        job_type=job_type,
        filename=filename,
        file_path=object_name,
        file_size=file_size,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if do_segmentation:
        task = process_full_pipeline_task.delay(
            job_id=str(job.id),
            file_path=object_name,
            source="minio",
            do_segmentation=True,
            segmentation_method=segmentation_method,
            language=language,
        )
    else:
        task = transcribe_audio_task.delay(
            job_id=str(job.id),
            file_path=object_name,
            source="minio",
            language=language,
        )

    job.celery_task_id = task.id
    await db.commit()
    await db.refresh(job)

    logger.info(f"Created job {job.id} for MinIO object {object_name}")
    return {
        "id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "filename": job.filename,
        "file_size": job.file_size,
        "file_path": job.file_path,
        "celery_task_id": job.celery_task_id,
        "error_message": job.error_message,
        "result": job.result,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "user_id": job.user_id,
    }


@router.post("/batch", response_model=list[JobResponse])
async def upload_batch(
    request: BatchUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    minio_service = get_minio_service()
    jobs = []

    for object_name in request.object_names:
        if not minio_service.file_exists(object_name):
            continue

        file_info = minio_service.get_file_info(object_name)
        filename = os.path.basename(object_name)

        job = Job(
            id=uuid.uuid4(),
            status="pending",
            job_type=request.job_type,
            filename=filename,
            file_path=object_name,
            file_size=file_info.get("size", 0),
        )
        db.add(job)
        jobs.append(job)

    await db.commit()
    for job in jobs:
        await db.refresh(job)

    for job in jobs:
        if request.do_segmentation:
            task = process_full_pipeline_task.delay(
                job_id=str(job.id),
                file_path=job.file_path,
                source="minio",
                do_segmentation=True,
                segmentation_method=request.segmentation_method,
                language=request.language,
            )
        else:
            task = transcribe_audio_task.delay(
                job_id=str(job.id),
                file_path=job.file_path,
                source="minio",
                language=request.language,
            )
        job.celery_task_id = task.id

    await db.commit()
    return [
        {
            "id": j.id,
            "status": j.status,
            "job_type": j.job_type,
            "filename": j.filename,
            "file_size": j.file_size,
            "file_path": j.file_path,
            "celery_task_id": j.celery_task_id,
            "error_message": j.error_message,
            "result": j.result,
            "created_at": j.created_at,
            "updated_at": j.updated_at,
            "user_id": j.user_id,
        }
        for j in jobs
    ]


@router.get("/health")
async def upload_health(minio_service: MinioService = Depends(get_minio_service)):
    try:
        minio_service.list_files(prefix="", recursive=False)
        disk_usage = os.statvfs(settings.UPLOAD_DIR) if os.path.exists(settings.UPLOAD_DIR) else None
        return {
            "status": "healthy",
            "minio": "connected",
            "disk_free_gb": round(disk_usage.f_frsize * disk_usage.f_bavail / (1024**3), 2) if disk_usage else None,
        }
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})
