from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class CorrelationRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    enabled: bool = True
    severity: str = "medium"
    category: str = "system"
    condition: dict[str, Any]
    threshold: int = 1
    time_window: int = 300
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    alert_title_template: str = "{rule_name} triggered"
    alert_description_template: str = "Rule {rule_name} triggered {count} times in {window} seconds."
    tags: Optional[list[str]] = None


class CorrelationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    condition: Optional[dict[str, Any]] = None
    threshold: Optional[int] = None
    time_window: Optional[int] = None
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    alert_title_template: Optional[str] = None
    alert_description_template: Optional[str] = None
    tags: Optional[list[str]] = None


class CorrelationRuleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: Optional[str] = None
    enabled: bool
    severity: str
    category: str
    condition: dict[str, Any]
    threshold: int
    time_window: int
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_triggered: Optional[datetime] = None
    trigger_count: int
    alert_title_template: str
    alert_description_template: str
    tags: Optional[list[str]] = None


class CorrelationRuleList(BaseModel):
    total: int
    items: list[CorrelationRuleRead]
