import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc

from app.database import get_db
from app.models.models import Job, TranscriptionResult, SegmentationResult
from app.schemas.schemas import JobResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/")
async def list_jobs(
    status: Optional[str] = Query(default=None),
    job_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    search: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job)
    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)
    if search:
        query = query.where(Job.filename.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    order_col = getattr(Job, sort_by, Job.created_at)
    query = query.order_by(desc(order_col) if sort_order == "desc" else asc(order_col))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "jobs": [
            {
                "id": j.id,
                "status": j.status,
                "job_type": j.job_type,
                "filename": j.filename,
                "file_size": j.file_size,
                "result": j.result,
                "error_message": j.error_message,
                "created_at": j.created_at,
                "updated_at": j.updated_at,
            }
            for j in jobs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats")
async def get_job_stats(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count(Job.id)))
    total = total_result.scalar()

    status_counts = await db.execute(
        select(Job.status, func.count(Job.id)).group_by(Job.status)
    )
    jobs_by_status = {}
    for row in status_counts.all():
        jobs_by_status[row[0]] = row[1]

    type_counts = await db.execute(
        select(Job.job_type, func.count(Job.id)).group_by(Job.job_type)
    )
    jobs_by_type = {}
    for row in type_counts.all():
        jobs_by_type[row[0]] = row[1]

    today = datetime.utcnow().date()
    today_result = await db.execute(
        select(func.count(Job.id)).where(func.date(Job.created_at) == today)
    )
    jobs_today = today_result.scalar()

    success_count = jobs_by_status.get("completed", 0)
    failed_count = jobs_by_status.get("failed", 0)
    total_finished = success_count + failed_count
    success_rate = round((success_count / total_finished * 100), 1) if total_finished > 0 else 0

    return {
        "total_jobs": total,
        "jobs_by_status": {"pending": jobs_by_status.get("pending", 0), "processing": jobs_by_status.get("processing", 0), "completed": success_count, "failed": failed_count},
        "jobs_by_type": jobs_by_type,
        "jobs_today": jobs_today,
        "success_rate": success_rate,
        "queue_depth": {"transcription": jobs_by_status.get("pending", 0), "segmentation": 0},
    }


@router.get("/recent")
async def get_recent_jobs(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).order_by(desc(Job.created_at)).limit(limit))
    jobs = result.scalars().all()
    return [
        {
            "id": j.id,
            "status": j.status,
            "job_type": j.job_type,
            "filename": j.filename,
            "file_size": j.file_size,
            "result": j.result,
            "error_message": j.error_message,
            "created_at": j.created_at,
            "updated_at": j.updated_at,
        }
        for j in jobs
    ]


@router.get("/health")
async def jobs_health():
    return {"status": "ok", "service": "jobs"}


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    transcription = await db.execute(
        select(TranscriptionResult).where(TranscriptionResult.job_id == job_id)
    )
    seg = await db.execute(
        select(SegmentationResult).where(SegmentationResult.job_id == job_id)
    )

    return {
        "id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "filename": job.filename,
        "file_size": job.file_size,
        "result": job.result,
        "error_message": job.error_message,
        "celery_task_id": job.celery_task_id,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.get("/{job_id}/status")
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": str(job.id),
        "status": job.status,
        "job_type": job.job_type,
        "celery_task_id": job.celery_task_id,
        "error_message": job.error_message,
    }

    if job.status == "processing":
        response["current_step"] = "processing"
        response["steps"] = ["downloading", "converting", "transcribing", "saving"]
    elif job.status == "completed":
        response["result"] = job.result

    return response


@router.delete("/{job_id}", status_code=204)
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.celery_task_id and job.status in ["pending", "processing"]:
        from app.tasks.celery_app import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    await db.delete(job)
    await db.commit()
    return Response(status_code=204)


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    job.status = "pending"
    job.error_message = None
    job.result = None
    await db.commit()

    from app.tasks.transcription_tasks import transcribe_audio_task
    task = transcribe_audio_task.delay(
        job_id=str(job.id),
        file_path=job.file_path,
        source="minio",
    )
    job.celery_task_id = task.id
    await db.commit()
    await db.refresh(job)

    return {
        "id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "filename": job.filename,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
