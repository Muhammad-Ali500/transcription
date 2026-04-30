from enum import Enum
from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    TRANSCRIPTION = "transcription"
    SEGMENTATION = "segmentation"


class JobCreate(BaseModel):
    filename: str
    job_type: "JobType"
    file_size: int
    source: str = "upload"


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    job_type: str
    filename: str
    file_size: int
    result: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int


class TranscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    segments: list[dict] = []
    created_at: datetime


class SegmentationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    segments: list[dict] = []
    total_segments: int
    metadata: dict = {}
    created_at: datetime


class WebSocketMessage(BaseModel):
    type: str
    job_id: UUID
    data: dict


class BatchUploadRequest(BaseModel):
    object_names: list[str]
    job_type: str = "transcription"
    language: Optional[str] = None
    do_segmentation: bool = False
    segmentation_method: str = "silence"
