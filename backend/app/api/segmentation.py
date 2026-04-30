import os
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, Body, HTTPException
from fastapi.responses import Response

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import settings
from app.models.models import Job, SegmentationResult
from app.services.segmentation_service import get_segmentation_service
from app.tasks.segmentation_tasks import process_full_pipeline_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/segmentation", tags=["segmentation"])


@router.post("/", status_code=201)
async def create_segmentation(
    file: UploadFile = File(...),
    method: str = Form(default="silence"),
    db: AsyncSession = Depends(get_db),
):
    from app.api.upload import validate_file_extension, detect_content_type

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

    from app.services.minio_service import get_minio_service
    minio_service = get_minio_service()
    minio_object_name = f"{unique_filename}"
    minio_service.upload_file(file_path, minio_object_name, detect_content_type(file.filename))

    job = Job(
        id=uuid.uuid4(),
        status="pending",
        job_type="segmentation",
        filename=file.filename,
        file_path=minio_object_name,
        file_size=file_size,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task = process_full_pipeline_task.delay(
        job_id=str(job.id),
        file_path=minio_object_name,
        source="minio",
        do_segmentation=True,
        segmentation_method=method,
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
async def get_segmentation(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.job_type != "segmentation":
        raise HTTPException(status_code=409, detail="Job is not a segmentation job")

    seg_result = await db.execute(
        select(SegmentationResult).where(SegmentationResult.job_id == job_id)
    )
    segmentation = seg_result.scalar_one_or_none()

    if job.status == "completed" and segmentation:
        return {
            "id": segmentation.id,
            "job_id": segmentation.job_id,
            "segments": segmentation.segments,
            "total_segments": segmentation.total_segments,
            "metadata": segmentation.metadata,
            "created_at": segmentation.created_at,
        }

    if job.status == "processing":
        return {"job_id": job_id, "status": "processing"}
    if job.status == "failed":
        raise HTTPException(status_code=500, detail=job.error_message)
    return {"job_id": job_id, "status": "pending"}


@router.get("/{job_id}/segments")
async def get_segments(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    min_duration: Optional[float] = Query(default=None),
    max_duration: Optional[float] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    seg_result = await db.execute(
        select(SegmentationResult).where(SegmentationResult.job_id == job_id)
    )
    segmentation = seg_result.scalar_one_or_none()
    if not segmentation or not segmentation.segments:
        return {"segments": [], "total": 0, "page": page, "page_size": page_size}

    segments = segmentation.segments
    if min_duration is not None:
        segments = [s for s in segments if s.get("duration", 0) >= min_duration]
    if max_duration is not None:
        segments = [s for s in segments if s.get("duration", 0) <= max_duration]
    if search:
        segments = [s for s in segments if search.lower() in s.get("text", "").lower()]

    total = len(segments)
    start = (page - 1) * page_size
    end = start + page_size
    return {"segments": segments[start:end], "total": total, "page": page, "page_size": page_size}


@router.post("/{job_id}/resegment")
async def resegment(
    job_id: str,
    method: str = Body(..., embed=True),
    params: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
):
    from app.models.models import TranscriptionResult

    transcription = await db.execute(
        select(TranscriptionResult).where(TranscriptionResult.job_id == job_id)
    )
    t_result = transcription.scalar_one_or_none()
    if not t_result:
        raise HTTPException(status_code=404, detail="Original transcription not found")

    new_job = Job(
        id=uuid.uuid4(),
        status="pending",
        job_type="segmentation",
        filename=f"resegment_{job_id}",
        file_path="",
        file_size=0,
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    from app.tasks.segmentation_tasks import segment_transcription_task
    task = segment_transcription_task.delay(
        job_id=str(new_job.id),
        transcription_result={"text": t_result.text, "language": t_result.language, "duration": t_result.duration, "segments": t_result.segments},
        method=method,
    )
    new_job.celery_task_id = task.id
    await db.commit()

    return {
        "id": new_job.id,
        "status": new_job.status,
        "job_type": new_job.job_type,
        "created_at": new_job.created_at,
        "updated_at": new_job.updated_at,
    }


@router.get("/{job_id}/export")
async def export_segments(
    job_id: str,
    format: str = Query(default="json"),
    db: AsyncSession = Depends(get_db),
):
    seg_result = await db.execute(
        select(SegmentationResult).where(SegmentationResult.job_id == job_id)
    )
    segmentation = seg_result.scalar_one_or_none()
    if not segmentation:
        raise HTTPException(status_code=404, detail="Segmentation not found")

    if format == "csv":
        lines = ["segment_id,start,end,duration,word_count,confidence,text"]
        for s in segmentation.segments or []:
            lines.append(f'{s.get("segment_id","")},{s.get("start",0)},{s.get("end",0)},{s.get("duration",0)},{s.get("word_count",0)},{s.get("confidence",0)},"{s.get("text","").replace(chr(10), " ")}"')
        content = "\n".join(lines)
        media_type = "text/csv"
        filename = f"segments_{job_id}.csv"
    elif format == "srt":
        lines = []
        for i, s in enumerate(segmentation.segments or [], 1):
            start = _fmt_srt(s.get("start", 0))
            end = _fmt_srt(s.get("end", 0))
            lines.append(f"{i}\n{start} --> {end}\n{s.get('text','')}\n")
        content = "\n".join(lines)
        media_type = "text/plain"
        filename = f"segments_{job_id}.srt"
    elif format == "txt":
        lines = []
        for s in segmentation.segments or []:
            lines.append(f"[{_fmt_ts(s.get('start',0))}-{_fmt_ts(s.get('end',0))}] {s.get('text','')}")
        content = "\n".join(lines)
        media_type = "text/plain"
        filename = f"segments_{job_id}.txt"
    else:
        import json
        content = json.dumps({"segments": segmentation.segments, "metadata": segmentation.metadata}, indent=2)
        media_type = "application/json"
        filename = f"segments_{job_id}.json"

    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/{job_id}/statistics")
async def get_segmentation_stats(job_id: str, db: AsyncSession = Depends(get_db)):
    seg_result = await db.execute(
        select(SegmentationResult).where(SegmentationResult.job_id == job_id)
    )
    segmentation = seg_result.scalar_one_or_none()
    if not segmentation or not segmentation.segments:
        return {"total_segments": 0, "statistics": {}}

    segments = segmentation.segments
    durations = [s.get("duration", 0) for s in segments]
    total_duration = sum(durations)
    avg_duration = total_duration / len(durations) if durations else 0

    ranges = {"0-5s": 0, "5-15s": 0, "15-30s": 0, "30-60s": 0, "60s+": 0}
    for d in durations:
        if d < 5:
            ranges["0-5s"] += 1
        elif d < 15:
            ranges["5-15s"] += 1
        elif d < 30:
            ranges["15-30s"] += 1
        elif d < 60:
            ranges["30-60s"] += 1
        else:
            ranges["60s+"] += 1

    return {
        "total_segments": len(segments),
        "average_segment_duration": round(avg_duration, 2),
        "shortest_segment": round(min(durations), 2) if durations else 0,
        "longest_segment": round(max(durations), 2) if durations else 0,
        "total_duration": round(total_duration, 2),
        "method_used": segmentation.metadata.get("method", "unknown"),
        "segments_by_duration_range": ranges,
    }


def _fmt_srt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_ts(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"
