"""
Pydantic schemas for ThreatIndicator model.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ThreatIndicatorCreate(BaseModel):
    indicator_type: Optional[str] = None  # auto-detected if omitted
    value: str
    confidence: int = 75
    severity: str = "medium"
    source: str = "manual"
    tags: Optional[list[str]] = None
    description: Optional[str] = None
    expiry: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class ThreatIndicatorUpdate(BaseModel):
    confidence: Optional[int] = None
    severity: Optional[str] = None
    tags: Optional[list[str]] = None
    description: Optional[str] = None
    expiry: Optional[datetime] = None
    raw_data: Optional[dict[str, Any]] = None


class ThreatIndicatorRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    indicator_type: str
    value: str
    confidence: int
    severity: str
    source: str
    tags: Optional[list] = None
    first_seen: datetime
    last_seen: datetime
    expiry: Optional[datetime] = None
    description: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None


class ThreatIndicatorList(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ThreatIndicatorRead]


class ThreatCheckRequest(BaseModel):
    value: str
    indicator_type: Optional[str] = None


class ThreatCheckResponse(BaseModel):
    found: bool
    indicator_type: str
    value: str
    confidence: Optional[int] = None
    severity: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[list[str]] = None
    description: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    expired: Optional[bool] = None
