from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AlertCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "medium"
    status: str = "open"
    rule_id: Optional[UUID] = None
    event_ids: Optional[list[str]] = None
    source_ips: Optional[list[str]] = None
    affected_users: Optional[list[str]] = None
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None


class AlertUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    resolved_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None


class AlertRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    created_at: datetime
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    rule_id: Optional[UUID] = None
    event_ids: Optional[list[str]] = None
    source_ips: Optional[list[str]] = None
    affected_users: Optional[list[str]] = None
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    escalated_at: Optional[datetime] = None
    sla_breach_at: Optional[datetime] = None
    hit_count: int = 1
    risk_score: Optional[float] = None
    dedup_key: Optional[str] = None


class AlertList(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[AlertRead]
