"""
Saved searches: analysts can bookmark named search queries and re-run them.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.saved_search import SavedSearch
from app.schemas.saved_search import (
    SavedSearchCreate,
    SavedSearchList,
    SavedSearchRead,
    SavedSearchUpdate,
)

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])
logger = logging.getLogger(__name__)


@router.get("", response_model=SavedSearchList, summary="List saved searches")
async def list_saved_searches(db: AsyncSession = Depends(get_db)) -> SavedSearchList:
    total_result = await db.execute(select(func.count()).select_from(SavedSearch))
    total = total_result.scalar() or 0

    result = await db.execute(select(SavedSearch).order_by(SavedSearch.name))
    items = list(result.scalars().all())
    return SavedSearchList(total=total, items=items)  # type: ignore[arg-type]


@router.post(
    "",
    response_model=SavedSearchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a saved search",
)
async def create_saved_search(
    data: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
) -> SavedSearch:
    import uuid

    existing = await db.execute(select(SavedSearch).where(SavedSearch.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Saved search '{data.name}' already exists",
        )

    entry = SavedSearch(
        id=uuid.uuid4(),
        name=data.name,
        description=data.description,
        query=data.query,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/{search_id}", response_model=SavedSearchRead, summary="Get a saved search")
async def get_saved_search(
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SavedSearch:
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")
    return entry


@router.put("/{search_id}", response_model=SavedSearchRead, summary="Update a saved search")
async def update_saved_search(
    search_id: UUID,
    data: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db),
) -> SavedSearch:
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")

    update_dict = data.model_dump(exclude_unset=True)

    if "name" in update_dict and update_dict["name"] != entry.name:
        existing = await db.execute(
            select(SavedSearch).where(SavedSearch.name == update_dict["name"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Saved search '{update_dict['name']}' already exists",
            )

    for field, value in update_dict.items():
        setattr(entry, field, value)

    entry.updated_at = datetime.now(timezone.utc)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete(
    "/{search_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved search",
)
async def delete_saved_search(
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")
    await db.delete(entry)
    await db.commit()
