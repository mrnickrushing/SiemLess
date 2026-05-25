"""
Watchlist router: manage persistent IP/user/hash/domain entries that
auto-tag matching ingested events.
"""
import logging
import uuid
from typing import Optional
from uuid import UUID as UUIDTYPE

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.watchlist import WatchlistEntry
from app.schemas.watchlist import (
    WatchlistEntryCreate,
    WatchlistEntryList,
    WatchlistEntryRead,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
logger = logging.getLogger(__name__)

_VALID_TYPES = {"ip", "user", "hash", "domain"}


@router.get("", response_model=WatchlistEntryList, summary="List watchlist entries")
async def list_watchlist(
    entry_type: Optional[str] = Query(None, description="Filter by type: ip, user, hash, domain"),
    q: Optional[str] = Query(None, description="Search value substring"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
) -> WatchlistEntryList:
    query = select(WatchlistEntry)
    count_query = select(func.count()).select_from(WatchlistEntry)

    filters = []
    if entry_type:
        filters.append(WatchlistEntry.entry_type == entry_type)
    if q:
        filters.append(WatchlistEntry.value.ilike(f"%{q}%"))

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(WatchlistEntry.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return WatchlistEntryList(total=total, items=items)  # type: ignore[arg-type]


@router.post(
    "",
    response_model=WatchlistEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a watchlist entry",
)
async def create_watchlist_entry(
    data: WatchlistEntryCreate,
    db: AsyncSession = Depends(get_db),
) -> WatchlistEntry:
    if data.entry_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"entry_type must be one of: {', '.join(sorted(_VALID_TYPES))}",
        )
    value = data.value.strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="value cannot be empty")

    existing = await db.execute(
        select(WatchlistEntry).where(
            WatchlistEntry.entry_type == data.entry_type,
            WatchlistEntry.value == value,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Watchlist entry {data.entry_type}:{value} already exists",
        )

    entry = WatchlistEntry(
        id=uuid.uuid4(),
        entry_type=data.entry_type,
        value=value,
        label=data.label,
        tags=data.tags or [],
        notes=data.notes,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get(
    "/{entry_id}",
    response_model=WatchlistEntryRead,
    summary="Get a watchlist entry",
)
async def get_watchlist_entry(
    entry_id: UUIDTYPE,
    db: AsyncSession = Depends(get_db),
) -> WatchlistEntry:
    result = await db.execute(select(WatchlistEntry).where(WatchlistEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist entry not found")
    return entry


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a watchlist entry",
)
async def delete_watchlist_entry(
    entry_id: UUIDTYPE,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(WatchlistEntry).where(WatchlistEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist entry not found")
    await db.delete(entry)
    await db.commit()
