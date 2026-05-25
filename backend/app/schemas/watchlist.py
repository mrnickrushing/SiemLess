from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class WatchlistEntryCreate(BaseModel):
    entry_type: str  # ip, user, hash, domain
    value: str
    label: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None


class WatchlistEntryRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    entry_type: str
    value: str
    label: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    created_at: datetime


class WatchlistEntryList(BaseModel):
    total: int
    items: list[WatchlistEntryRead]
