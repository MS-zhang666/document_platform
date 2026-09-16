from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
)


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str

    postgres: str

    redis: str


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str

    original_filename: str

    file_type: str

    content_type: str

    size_bytes: int

    parse_status: str

    last_job_id: Optional[str]

    page_count: Optional[int]

    char_count: Optional[int]

    created_at: datetime

    parsed_at: Optional[datetime]


class JobCreatedResponse(BaseModel):
    job_id: str

    document_id: str

    status: str


class JobStatusResponse(BaseModel):
    job_id: str

    document_id: str

    status: str

    progress: int

    message: str

    attempt: int

    max_attempts: int

    cancel_requested: bool

    error: Optional[str] = None

    retry_of: Optional[str] = None
