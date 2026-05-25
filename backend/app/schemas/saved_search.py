from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SavedSearchCreate(BaseModel):
    name: str
    description: Optional[str] = None
    query: str


class SavedSearchUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    query: Optional[str] = None


class SavedSearchRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: Optional[str] = None
    query: str
    created_at: datetime
    updated_at: datetime


class SavedSearchList(BaseModel):
    total: int
    items: list[SavedSearchRead]
