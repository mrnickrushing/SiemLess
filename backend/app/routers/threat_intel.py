"""
Threat Intel router: CRUD for indicators and bulk import/check endpoints.
"""
import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.threat_intel import ThreatIndicator
from app.services.threat_intel import ThreatIntelService, _detect_indicator_type, threat_intel_service

router = APIRouter(prefix="/threat-intel", tags=["threat-intel"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas (inline for this router)
# ---------------------------------------------------------------------------

class IndicatorCreate(BaseModel):
    indicator_type: Optional[str] = None  # auto-detected if omitted
    value: str
    confidence: int = 75
    severity: str = "medium"
    source: str = "manual"
    tags: Optional[list[str]] = None
    description: Optional[str] = None
    expiry: Optional[datetime] = None
    raw_data: Optional[dict] = None


class IndicatorRead(BaseModel):
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
    raw_data: Optional[dict] = None


class CheckRequest(BaseModel):
    value: str
    indicator_type: Optional[str] = None


class BulkImportRequest(BaseModel):
    indicators: list[IndicatorCreate]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats", summary="Threat indicator statistics")
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Returns counts by type, severity, and active/total totals."""
    now = datetime.now(timezone.utc)

    total = (await db.execute(select(func.count()).select_from(ThreatIndicator))).scalar() or 0

    active = (await db.execute(
        select(func.count()).select_from(ThreatIndicator).where(
            (ThreatIndicator.expiry.is_(None)) | (ThreatIndicator.expiry > now)
        )
    )).scalar() or 0

    by_type_rows = (await db.execute(
        select(ThreatIndicator.indicator_type, func.count().label("cnt"))
        .group_by(ThreatIndicator.indicator_type)
    )).all()
    by_type = {row.indicator_type: row.cnt for row in by_type_rows}

    by_severity_rows = (await db.execute(
        select(ThreatIndicator.severity, func.count().label("cnt"))
        .group_by(ThreatIndicator.severity)
    )).all()
    by_severity = {row.severity: row.cnt for row in by_severity_rows}

    return {"total": total, "active": active, "by_type": by_type, "by_severity": by_severity}


@router.get("/check", summary="Check if a value is a known threat indicator")
async def check_indicator_get(
    value: str = Query(..., description="IP, domain, hash, or URL to check"),
    indicator_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET convenience wrapper for the threat check used by the UI quick-check."""
    result = await threat_intel_service.check_indicator(db, value.strip(), indicator_type)
    await db.commit()
    return result


@router.get("", response_model=dict, summary="List threat indicators")
async def list_indicators(
    indicator_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search value substring"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(ThreatIndicator)
    count_query = select(func.count()).select_from(ThreatIndicator)

    filters = []
    if indicator_type:
        filters.append(ThreatIndicator.indicator_type == indicator_type)
    if severity:
        filters.append(ThreatIndicator.severity == severity)
    if source:
        filters.append(ThreatIndicator.source == source)
    if q:
        filters.append(ThreatIndicator.value.ilike(f"%{q}%"))

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(ThreatIndicator.last_seen.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [IndicatorRead.model_validate(i).model_dump() for i in items],
    }


@router.post(
    "/indicators",
    response_model=IndicatorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a threat indicator",
)
async def create_indicator(
    indicator_data: IndicatorCreate,
    db: AsyncSession = Depends(get_db),
) -> ThreatIndicator:
    value = indicator_data.value.strip()
    if not value:
        raise HTTPException(status_code=400, detail="Indicator value cannot be empty")

    indicator_type = indicator_data.indicator_type or _detect_indicator_type(value)
    if indicator_type == "unknown":
        raise HTTPException(status_code=400, detail="Cannot detect indicator type; provide indicator_type explicitly")

    # Check uniqueness
    existing = await db.execute(
        select(ThreatIndicator).where(
            ThreatIndicator.indicator_type == indicator_type,
            ThreatIndicator.value == value,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Indicator {indicator_type}:{value} already exists",
        )

    now = datetime.now(timezone.utc)
    indicator = ThreatIndicator(
        id=uuid.uuid4(),
        indicator_type=indicator_type,
        value=value,
        confidence=indicator_data.confidence,
        severity=indicator_data.severity,
        source=indicator_data.source,
        tags=indicator_data.tags or [],
        first_seen=now,
        last_seen=now,
        expiry=indicator_data.expiry,
        description=indicator_data.description or "",
        raw_data=indicator_data.raw_data,
    )
    db.add(indicator)
    await db.commit()
    await db.refresh(indicator)
    return indicator


@router.get("/indicators/{indicator_id}", response_model=IndicatorRead, summary="Get a single indicator")
async def get_indicator(
    indicator_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ThreatIndicator:
    result = await db.execute(
        select(ThreatIndicator).where(ThreatIndicator.id == indicator_id)
    )
    indicator = result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")
    return indicator


@router.delete(
    "/indicators/{indicator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a threat indicator",
)
async def delete_indicator(
    indicator_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ThreatIndicator).where(ThreatIndicator.id == indicator_id)
    )
    indicator = result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")
    await db.delete(indicator)
    await db.commit()


@router.post("/check", summary="Check if a value is a known threat indicator")
async def check_indicator(
    request: CheckRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Check whether an IP, domain, file hash, etc. is in the threat intel database
    and optionally query external feeds if API keys are configured.
    """
    result = await threat_intel_service.check_indicator(
        db, request.value.strip(), request.indicator_type
    )
    await db.commit()
    return result


@router.post("/import", summary="Bulk import indicators from JSON list or CSV file")
async def bulk_import(
    file: Optional[UploadFile] = File(None),
    body: Optional[BulkImportRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Import threat indicators in bulk.

    Accepts either:
    - A JSON body with a list of indicator objects
    - A CSV file upload with columns: value, indicator_type, severity, confidence, source, description, tags

    Returns the count of newly imported indicators.
    """
    indicators: list[dict] = []

    if file:
        content = await file.read()
        text = content.decode("utf-8", errors="replace")

        if file.filename and file.filename.endswith(".json"):
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    indicators = data
                elif isinstance(data, dict) and "indicators" in data:
                    indicators = data["indicators"]
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")
        else:
            # Try CSV
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                value = row.get("value", "").strip()
                if value:
                    tags_raw = row.get("tags", "")
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
                    indicators.append({
                        "value": value,
                        "indicator_type": row.get("indicator_type") or _detect_indicator_type(value),
                        "severity": row.get("severity", "medium"),
                        "confidence": int(row.get("confidence", 75)),
                        "source": row.get("source", "import"),
                        "description": row.get("description", ""),
                        "tags": tags,
                    })
    elif body:
        indicators = [i.model_dump() for i in body.indicators]
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a file upload or a JSON body with indicators list",
        )

    if not indicators:
        return {"imported": 0, "total": 0}

    imported = await threat_intel_service.bulk_import_indicators(db, indicators)
    await db.commit()

    return {"imported": imported, "total": len(indicators), "skipped": len(indicators) - imported}


# ---------------------------------------------------------------------------
# Short-path aliases used by the frontend UI
# These must come after all fixed-path routes (/stats, /check, /indicators/*)
# to avoid FastAPI matching them as indicator IDs.
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=IndicatorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a threat indicator (short-path alias)",
)
async def create_indicator_alias(
    indicator_data: IndicatorCreate,
    db: AsyncSession = Depends(get_db),
) -> ThreatIndicator:
    return await create_indicator(indicator_data, db)


@router.delete(
    "/{indicator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a threat indicator (short-path alias)",
)
async def delete_indicator_alias(
    indicator_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    return await delete_indicator(indicator_id, db)
