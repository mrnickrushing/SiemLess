from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SecurityEventCreate(BaseModel):
    timestamp: Optional[datetime] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    source_port: Optional[int] = None
    destination_port: Optional[int] = None
    hostname: Optional[str] = None
    log_source: str = "api"
    log_type: str = "generic"
    severity: str = "low"
    category: str = "system"
    message: Optional[str] = None
    raw_log: Optional[str] = None
    parsed_fields: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None
    country: Optional[str] = None
    user: Optional[str] = None
    process: Optional[str] = None
    action: Optional[str] = None


class SecurityEventUpdate(BaseModel):
    severity: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    parsed_fields: Optional[dict[str, Any]] = None


class SecurityEventRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    timestamp: datetime
    received_at: datetime
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    source_port: Optional[int] = None
    destination_port: Optional[int] = None
    hostname: Optional[str] = None
    log_source: str
    log_type: str
    severity: str
    category: str
    message: Optional[str] = None
    raw_log: Optional[str] = None
    parsed_fields: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None
    country: Optional[str] = None
    user: Optional[str] = None
    process: Optional[str] = None
    action: Optional[str] = None
    risk_score: Optional[float] = None
    normalized_fields: Optional[dict[str, Any]] = None


class SecurityEventList(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SecurityEventRead]


class RawLogIngest(BaseModel):
    raw_log: str
    log_source: str = "api"
    hint: Optional[str] = None  # hint for log type detection


class BatchIngest(BaseModel):
    events: list[SecurityEventCreate] = Field(..., max_length=1000)
