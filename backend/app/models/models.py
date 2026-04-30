import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, BigInteger, JSON, DateTime, Integer, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_job_type", "job_type"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_celery_task_id", "celery_task_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False, default="pending")
    job_type = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user_id = Column(String, nullable=True)

    transcription_result = relationship("TranscriptionResult", back_populates="job", cascade="all, delete-orphan")
    segmentation_result = relationship("SegmentationResult", back_populates="job", cascade="all, delete-orphan")


class TranscriptionResult(Base):
    __tablename__ = "transcription_results"
    __table_args__ = (
        Index("idx_transcription_job_id", "job_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    language = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    segments = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="transcription_result")


class SegmentationResult(Base):
    __tablename__ = "segmentation_results"
    __table_args__ = (
        Index("idx_segmentation_job_id", "job_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    segments = Column(JSON, nullable=True)
    total_segments = Column(Integer, nullable=True)
    seg_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="segmentation_result")
