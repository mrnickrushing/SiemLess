"""Schemas for Case Management."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class CaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "medium"
    assigned_to: Optional[str] = None
    tags: Optional[dict] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    assigned_to: Optional[str] = None
    tags: Optional[dict] = None
    closed_at: Optional[datetime] = None


class CaseRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    title: str
    description: Optional[str] = None
    status: str
    severity: str
    assigned_to: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    tags: Optional[dict] = None


class CaseList(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CaseRead]


class CaseCommentCreate(BaseModel):
    author: str
    body: str


class CaseCommentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    case_id: str
    author: str
    body: str
    created_at: datetime


class CaseArtifactCreate(BaseModel):
    artifact_type: str  # ip/hash/file/url/domain
    value: str
    notes: Optional[str] = None


class CaseArtifactRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    case_id: str
    artifact_type: str
    value: str
    notes: Optional[str] = None
    created_at: datetime


class LinkEventsRequest(BaseModel):
    event_ids: list[str]


class LinkAlertsRequest(BaseModel):
    alert_ids: list[str]


class CaseTimelineItem(BaseModel):
    type: str  # event/alert/comment
    id: str
    timestamp: datetime
    summary: str
    detail: Optional[Any] = None
