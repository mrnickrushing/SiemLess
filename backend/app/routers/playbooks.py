"""SOAR Playbook router."""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.soar import Playbook, PlaybookRun
from app.services.playbook_engine import playbook_engine

router = APIRouter(prefix="/playbooks", tags=["playbooks"])
logger = logging.getLogger(__name__)


@router.get("", summary="List playbooks")
async def list_playbooks(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list:
    result = await db.execute(select(Playbook))
    return [_pb_to_dict(p) for p in result.scalars()]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create playbook")
async def create_playbook(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    pb = Playbook(
        id=str(uuid.uuid4()),
        name=payload.get("name", "Unnamed Playbook"),
        description=payload.get("description"),
        trigger_type=payload.get("trigger_type", "manual"),
        trigger_config=payload.get("trigger_config", {}),
        steps=payload.get("steps", []),
        enabled=payload.get("enabled", True),
    )
    db.add(pb)
    await db.commit()
    await db.refresh(pb)
    return _pb_to_dict(pb)


@router.get("/{playbook_id}", summary="Get playbook")
async def get_playbook(
    playbook_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = result.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return _pb_to_dict(pb)


@router.patch("/{playbook_id}", summary="Update playbook")
async def update_playbook(
    playbook_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = result.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    for field in ("name", "description", "trigger_type", "trigger_config", "steps", "enabled"):
        if field in payload:
            setattr(pb, field, payload[field])
    await db.commit()
    await db.refresh(pb)
    return _pb_to_dict(pb)


@router.delete("/{playbook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playbook(
    playbook_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = result.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    await db.delete(pb)
    await db.commit()


@router.get("/{playbook_id}/runs", summary="Get playbook run history")
async def get_runs(
    playbook_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count()).select_from(PlaybookRun).where(PlaybookRun.playbook_id == playbook_id)
    )
    total = count_result.scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(
        select(PlaybookRun)
        .where(PlaybookRun.playbook_id == playbook_id)
        .order_by(PlaybookRun.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    runs = result.scalars().all()
    return {
        "total": total,
        "items": [_run_to_dict(r) for r in runs],
    }


@router.post("/{playbook_id}/trigger", status_code=status.HTTP_202_ACCEPTED, summary="Manually trigger playbook")
async def trigger_playbook(
    playbook_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> dict:
    alert_id = payload.get("alert_id")
    try:
        run_id = await playbook_engine.trigger_manual(db, playbook_id, alert_id, username)
        return {"run_id": run_id, "status": "triggered"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _pb_to_dict(pb: Playbook) -> dict:
    return {
        "id": pb.id,
        "name": pb.name,
        "description": pb.description,
        "trigger_type": pb.trigger_type,
        "trigger_config": pb.trigger_config,
        "steps": pb.steps,
        "enabled": pb.enabled,
        "run_count": pb.run_count,
        "created_at": pb.created_at.isoformat(),
        "last_triggered_at": pb.last_triggered_at.isoformat() if pb.last_triggered_at else None,
    }


def _run_to_dict(r: PlaybookRun) -> dict:
    return {
        "id": r.id,
        "playbook_id": r.playbook_id,
        "alert_id": r.alert_id,
        "triggered_by": r.triggered_by,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "status": r.status,
        "step_results": r.step_results,
        "error_message": r.error_message,
    }
