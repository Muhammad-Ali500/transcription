import logging
import uuid

from app.tasks.celery_app import celery_app
from app.services.segmentation_service import get_segmentation_service

logger = logging.getLogger(__name__)


def update_job_status(job_id: str, status: str, error_message: str = None, result: dict = None):
    from app.database import sync_session
    from app.models.models import Job
    from sqlalchemy import update

    with sync_session() as session:
        stmt = update(Job).where(Job.id == job_id).values(
            status=status,
            error_message=error_message,
            result=result,
        )
        session.execute(stmt)
        session.commit()


def save_segmentation_result(job_id, segmentation_result):
    from app.database import sync_session
    from app.models.models import SegmentationResult

    with sync_session() as session:
        record = SegmentationResult(
            id=uuid.uuid4(),
            job_id=job_id,
            segments=segmentation_result.get("segments", []),
            total_segments=segmentation_result.get("total_segments", 0),
            seg_metadata=segmentation_result.get("metadata", {}),
        )
        session.add(record)
        session.commit()


@celery_app.task(
    name="segmentation.segment_transcription",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def segment_transcription_task(self, job_id: str, transcription_result: dict, method: str = "silence") -> dict:
    logger.info(f"Starting segmentation task for job {job_id}")
    try:
        update_job_status(job_id, "processing")

        segmentation_service = get_segmentation_service()
        result = segmentation_service.process_segmentation(transcription_result, method=method)

        save_segmentation_result(job_id, result)

        summary = {
            "total_segments": result["total_segments"],
            "method": result["metadata"].get("method", method),
            "total_duration": result["metadata"].get("total_duration", 0),
        }
        update_job_status(job_id, "completed", result=summary)

        logger.info(f"Segmentation completed for job {job_id}: {result['total_segments']} segments")
        return result

    except Exception as e:
        logger.error(f"Segmentation failed for job {job_id}: {e}")
        update_job_status(job_id, "failed", error_message=str(e))
        raise self.retry(exc=e, countdown=30)


@celery_app.task(name="pipeline.process_full", bind=True, max_retries=3, default_retry_delay=30, acks_late=True)
def process_full_pipeline_task(
    self,
    job_id: str,
    file_path: str,
    source: str = "local",
    do_segmentation: bool = True,
    segmentation_method: str = "silence",
    language: str = None,
) -> dict:
    from app.tasks.transcription_tasks import transcribe_audio_task

    logger.info(f"Starting full pipeline for job {job_id}")
    try:
        transcription_result = transcribe_audio_task.run(
            job_id=job_id,
            file_path=file_path,
            source=source,
            language=language,
        )

        if do_segmentation and transcription_result:
            update_job_status(job_id, "processing")
            segmentation_result = segment_transcription_task.run(
                job_id=job_id,
                transcription_result=transcription_result,
                method=segmentation_method,
            )
            return {
                "transcription": transcription_result,
                "segmentation": segmentation_result,
            }

        return {"transcription": transcription_result}

    except Exception as e:
        logger.error(f"Pipeline failed for job {job_id}: {e}")
        update_job_status(job_id, "failed", error_message=str(e))
        raise self.retry(exc=e, countdown=30)
