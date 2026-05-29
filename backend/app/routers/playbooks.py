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
    """
    List all playbooks and return them as serialized dictionaries.
    
    Returns:
        list[dict]: A list of playbook dictionaries. Each dictionary contains:
            - id: playbook UUID string
            - name: playbook name
            - description: optional description
            - trigger_type: trigger type string
            - trigger_config: trigger configuration object
            - steps: list of step definitions
            - enabled: boolean flag
            - run_count: integer count of runs
            - created_at: ISO 8601 timestamp string
            - last_triggered_at: ISO 8601 timestamp string or None
    """
    result = await db.execute(select(Playbook))
    return [_pb_to_dict(p) for p in result.scalars()]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create playbook")
async def create_playbook(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Create a new playbook record from the provided payload and return its serialized representation.
    
    Parameters:
        payload (dict): Playbook attributes. Recognized keys:
            - `name` (str): Playbook name; defaults to `"Unnamed Playbook"`.
            - `description` (str | None): Optional human-readable description.
            - `trigger_type` (str): Trigger mechanism; defaults to `"manual"`.
            - `trigger_config` (dict): Trigger configuration; defaults to an empty dict.
            - `steps` (list): Ordered list of step definitions; defaults to an empty list.
            - `enabled` (bool): Whether the playbook is active; defaults to `True`.
    
    Returns:
        dict: Serialized playbook including `id`, `name`, `description`, `trigger_type`, `trigger_config`, `steps`, `enabled`, `run_count`, `created_at`, and `last_triggered_at`.
    """
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
    """
    Retrieve a single playbook by ID and return its serialized dictionary representation.
    
    Returns:
        dict: Serialized playbook with keys `id`, `name`, `description`, `trigger_type`, `trigger_config`, `steps`, `enabled`, `run_count`, `created_at` (ISO string), and `last_triggered_at` (ISO string or `None`).
    
    Raises:
        HTTPException: 404 if no playbook exists with the given `playbook_id`.
    """
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
    """
    Update fields of an existing playbook.
    
    Parameters:
        playbook_id (str): Identifier of the playbook to update.
        payload (dict): Partial mapping of fields to update. Accepted keys:
            "name", "description", "trigger_type", "trigger_config", "steps", "enabled".
    
    Returns:
        dict: Serialized representation of the updated playbook.
    
    Raises:
        HTTPException: 404 if a playbook with `playbook_id` does not exist.
    """
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
    """
    Delete a playbook by its ID.
    
    Removes the matching playbook record from the database and commits the change.
    
    Parameters:
        playbook_id (str): The UUID string identifier of the playbook to delete.
    
    Raises:
        HTTPException: status 404 if no playbook with the given ID exists.
    """
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
    """
    Return paginated run history for the specified playbook.
    
    Parameters:
    	playbook_id (str): ID of the playbook whose runs are requested.
    	page (int): 1-based page number to retrieve.
    	page_size (int): Maximum number of runs to include on a page (1–100).
    
    Returns:
    	dict: Mapping with keys `"total"` (total number of runs) and `"items"` (list of run dictionaries as returned by `_run_to_dict`).
    """
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
    """
    Manually triggers a run of the specified playbook.
    
    Parameters:
        payload (dict): Optional payload for the trigger. May include the key `"alert_id"` to associate the run with an existing alert.
    
    Returns:
        dict: A dictionary containing `"run_id"` (the created run's identifier) and `"status"` set to `"triggered"`.
    
    Raises:
        HTTPException: Raised with status 404 when the playbook cannot be found or the trigger cannot be created.
    """
    alert_id = payload.get("alert_id")
    try:
        run_id = await playbook_engine.trigger_manual(db, playbook_id, alert_id, username)
        return {"run_id": run_id, "status": "triggered"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _pb_to_dict(pb: Playbook) -> dict:
    """
    Serialize a Playbook ORM instance into a JSON-serializable dictionary.
    
    Parameters:
        pb (Playbook): Playbook model instance to serialize.
    
    Returns:
        dict: Mapping with the playbook's fields:
            - `id`: playbook identifier (string)
            - `name`: playbook name
            - `description`: optional description
            - `trigger_type`: trigger type string
            - `trigger_config`: trigger configuration object
            - `steps`: list of step definitions
            - `enabled`: boolean enabled flag
            - `run_count`: integer number of runs
            - `created_at`: ISO 8601 string of creation time
            - `last_triggered_at`: ISO 8601 string of last triggered time or `None`
    """
    return {
        "id": pb.id,
        "name": pb.name,
        "description": pb.description,
        "trigger_type": pb.trigger_type,
        "trigger_on": pb.trigger_type,
        "trigger_config": pb.trigger_config,
        "steps": pb.steps or [],
        "enabled": pb.enabled,
        "run_count": pb.run_count,
        "created_at": pb.created_at.isoformat(),
        "last_triggered_at": pb.last_triggered_at.isoformat() if pb.last_triggered_at else None,
        "last_run_at": pb.last_triggered_at.isoformat() if pb.last_triggered_at else None,
        "updated_at": pb.created_at.isoformat(),
    }


def _run_to_dict(r: PlaybookRun) -> dict:
    """
    Convert a PlaybookRun ORM instance into a JSON-serializable dictionary.
    
    Parameters:
        r (PlaybookRun): PlaybookRun ORM instance to serialize.
    
    Returns:
        dict: Dictionary with the playbook run fields:
            - `id`: run identifier.
            - `playbook_id`: associated playbook identifier.
            - `alert_id`: associated alert identifier or `None`.
            - `triggered_by`: username that triggered the run.
            - `started_at`: ISO 8601 string of the start time.
            - `finished_at`: ISO 8601 string of the finish time or `None` if not finished.
            - `status`: run status.
            - `step_results`: results for each step.
            - `error_message`: error message if the run failed, otherwise `None`.
    """
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
        "error": r.error_message,
    }
