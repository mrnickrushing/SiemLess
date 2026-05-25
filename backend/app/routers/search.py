"""
Search router: full-text and structured search across security events.

Supports a simple query syntax:
  - Plain text: searches message and raw_log fields (ILIKE)
  - Field:value pairs: e.g. "severity:high AND source_ip:10.0.0.1"
  - Operators: AND (default), OR
"""
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import SecurityEvent
from app.schemas.event import SecurityEventList, SecurityEventRead

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)

# Known filterable fields and their model attributes
FIELD_MAP = {
    "severity": SecurityEvent.severity,
    "category": SecurityEvent.category,
    "log_type": SecurityEvent.log_type,
    "log_source": SecurityEvent.log_source,
    "source_ip": SecurityEvent.source_ip,
    "destination_ip": SecurityEvent.destination_ip,
    "hostname": SecurityEvent.hostname,
    "user": SecurityEvent.user,
    "process": SecurityEvent.process,
    "action": SecurityEvent.action,
    "country": SecurityEvent.country,
}

_FIELD_VALUE_RE = re.compile(r'(\w+):"([^"]+)"|(\w+):(\S+)')
_AND_RE = re.compile(r'\s+AND\s+', re.IGNORECASE)
_OR_RE = re.compile(r'\s+OR\s+', re.IGNORECASE)


def _parse_query(q: str) -> tuple[list[tuple[str, str]], list[str], str]:
    """
    Parse a query string into:
    - field_filters: list of (field, value) tuples for known fields
    - text_terms: list of free-text search terms
    - operator: "AND" or "OR"
    """
    # Detect top-level operator
    operator = "AND"
    if _OR_RE.search(q):
        operator = "OR"

    # Split on AND/OR
    parts = re.split(r'\s+(?:AND|OR)\s+', q, flags=re.IGNORECASE)

    field_filters: list[tuple[str, str]] = []
    text_terms: list[str] = []

    for part in parts:
        part = part.strip()
        m = _FIELD_VALUE_RE.match(part)
        if m:
            field = (m.group(1) or m.group(3)).lower()
            value = m.group(2) or m.group(4)
            if field in FIELD_MAP:
                field_filters.append((field, value))
            else:
                text_terms.append(part)
        elif part:
            text_terms.append(part)

    return field_filters, text_terms, operator


def _build_highlight(text_content: Optional[str], terms: list[str], max_len: int = 200) -> str:
    """Return a snippet of text_content with the first matched term highlighted."""
    if not text_content or not terms:
        return (text_content or "")[:max_len]

    text_lower = text_content.lower()
    for term in terms:
        idx = text_lower.find(term.lower())
        if idx != -1:
            start = max(0, idx - 60)
            end = min(len(text_content), idx + len(term) + 60)
            snippet = text_content[start:end]
            highlight = snippet.replace(
                text_content[idx : idx + len(term)],
                f"**{text_content[idx : idx + len(term)]}**",
                1,
            )
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text_content) else ""
            return f"{prefix}{highlight}{suffix}"

    return text_content[:max_len]


@router.get("", response_model=dict, summary="Full-text and structured search across events")
async def search_events(
    q: str = Query(..., min_length=1, description="Search query. Supports field:value AND/OR syntax."),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Search security events using a flexible query syntax.

    Examples:
    - `failed ssh` – free text search
    - `severity:high AND source_ip:10.0.0.1` – field filters
    - `severity:critical OR severity:high` – OR operator
    - `user:admin AND action:failed` – combined filters
    """
    field_filters, text_terms, operator = _parse_query(q.strip())

    base_query = select(SecurityEvent)
    count_base = select(func.count()).select_from(SecurityEvent)

    # Time range filters
    time_filters = []
    if start_time:
        time_filters.append(SecurityEvent.timestamp >= start_time)
    if end_time:
        time_filters.append(SecurityEvent.timestamp <= end_time)

    # Build field filter conditions
    field_conditions = []
    for field, value in field_filters:
        col = FIELD_MAP[field]
        field_conditions.append(col.ilike(f"%{value}%"))

    # Build full-text conditions
    text_conditions = []
    for term in text_terms:
        term_lower = f"%{term}%"
        text_conditions.append(
            or_(
                SecurityEvent.message.ilike(term_lower),
                SecurityEvent.raw_log.ilike(term_lower),
                SecurityEvent.hostname.ilike(term_lower),
                SecurityEvent.source_ip.ilike(term_lower),
                SecurityEvent.user.ilike(term_lower),
            )
        )

    # Combine all conditions
    all_conditions = time_filters.copy()

    if operator == "OR":
        or_parts = field_conditions + text_conditions
        if or_parts:
            all_conditions.append(or_(*or_parts))
    else:
        all_conditions.extend(field_conditions)
        all_conditions.extend(text_conditions)

    if all_conditions:
        base_query = base_query.where(*all_conditions)
        count_base = count_base.where(*all_conditions)

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    base_query = base_query.order_by(SecurityEvent.timestamp.desc()).offset(offset).limit(page_size)
    result = await db.execute(base_query)
    events = list(result.scalars().all())

    # Build response with highlights
    items = []
    all_terms = text_terms + [v for _, v in field_filters]
    for event in events:
        event_dict = {
            "id": str(event.id),
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "received_at": event.received_at.isoformat() if event.received_at else None,
            "source_ip": event.source_ip,
            "destination_ip": event.destination_ip,
            "source_port": event.source_port,
            "destination_port": event.destination_port,
            "hostname": event.hostname,
            "log_source": event.log_source,
            "log_type": event.log_type,
            "severity": event.severity,
            "category": event.category,
            "message": event.message,
            "raw_log": event.raw_log,
            "parsed_fields": event.parsed_fields,
            "tags": event.tags,
            "country": event.country,
            "user": event.user,
            "process": event.process,
            "action": event.action,
            "_highlight": {
                "message": _build_highlight(event.message, all_terms),
                "raw_log": _build_highlight(event.raw_log, all_terms),
            },
        }
        items.append(event_dict)

    return {
        "query": q,
        "parsed": {
            "field_filters": field_filters,
            "text_terms": text_terms,
            "operator": operator,
        },
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
