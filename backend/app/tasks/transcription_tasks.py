import os
import logging

from app.tasks.celery_app import celery_app
from app.config import settings
from app.services.transcription_service import get_transcription_service, TranscriptionError

logger = logging.getLogger(__name__)


def update_job_status(job_id: str, status: str, error_message: str = None, result: dict = None, celery_task_id: str = None):
    from app.database import sync_session
    from app.models.models import Job
    from sqlalchemy import update

    with sync_session() as session:
        stmt = update(Job).where(Job.id == job_id).values(
            status=status,
            error_message=error_message,
            result=result,
            celery_task_id=celery_task_id,
        )
        session.execute(stmt)
        session.commit()


def save_transcription_result(job_id, transcription_result):
    from app.database import sync_session
    from app.models.models import TranscriptionResult
    import uuid

    with sync_session() as session:
        record = TranscriptionResult(
            id=uuid.uuid4(),
            job_id=job_id,
            text=transcription_result["text"],
            language=transcription_result.get("language"),
            duration=transcription_result.get("duration"),
            segments=transcription_result.get("segments", []),
        )
        session.add(record)
        session.commit()


@celery_app.task(
    name="transcription.transcribe_audio",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def transcribe_audio_task(self, job_id: str, file_path: str, source: str = "local", language: str = None) -> dict:
    logger.info(f"Starting transcription task for job {job_id}")
    try:
        update_job_status(job_id, "processing", celery_task_id=self.request.id)

        self.update_state(state="PROGRESS", meta={"progress": 0.1, "step": "initializing"})

        audio_path = file_path
        if source == "minio":
            self.update_state(state="PROGRESS", meta={"progress": 0.2, "step": "downloading"})
            from app.services.minio_service import get_minio_service
            minio_service = get_minio_service()
            tmp_dir = settings.UPLOAD_DIR
            os.makedirs(tmp_dir, exist_ok=True)
            local_path = os.path.join(tmp_dir, os.path.basename(file_path))
            minio_service.download_file(file_path, local_path)
            audio_path = local_path

        self.update_state(state="PROGRESS", meta={"progress": 0.4, "step": "transcribing"})
        transcription_service = get_transcription_service()
        result = transcription_service.transcribe(audio_path, language)

        self.update_state(state="PROGRESS", meta={"progress": 0.8, "step": "saving"})
        save_transcription_result(job_id, result)

        summary = {
            "text_length": len(result["text"]),
            "language": result["language"],
            "duration": result["duration"],
            "segments_count": len(result["segments"]),
            "processing_time": result["processing_time"],
        }
        update_job_status(job_id, "completed", result=summary)

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "completed"})
        logger.info(f"Transcription completed for job {job_id} in {result['processing_time']}s")

        if source == "minio" and os.path.exists(audio_path):
            os.remove(audio_path)

        return result

    except Exception as e:
        logger.error(f"Transcription failed for job {job_id}: {e}")
        update_job_status(job_id, "failed", error_message=str(e))
        raise self.retry(exc=e, countdown=30)
