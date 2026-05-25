"""
Stats router: aggregated statistics and dashboard metrics.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, func, select, text, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import Alert
from app.models.event import SecurityEvent
from app.models.rule import CorrelationRule
from app.models.threat_intel import ThreatIndicator

router = APIRouter(prefix="/stats", tags=["stats"])
logger = logging.getLogger(__name__)


@router.get("/overview", summary="SIEM overview: event counts, alerts, top sources")
async def get_overview(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns key metrics for the SIEM dashboard:
    - Total events today
    - Open alerts count
    - Total rules (enabled/disabled)
    - Top 5 source IPs by event count
    - Events by severity (today)
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total events today
    events_today_result = await db.execute(
        select(func.count()).select_from(SecurityEvent).where(SecurityEvent.timestamp >= today_start)
    )
    events_today = events_today_result.scalar() or 0

    # Total events overall
    total_events_result = await db.execute(select(func.count()).select_from(SecurityEvent))
    total_events = total_events_result.scalar() or 0

    # Open alerts
    open_alerts_result = await db.execute(
        select(func.count()).select_from(Alert).where(Alert.status == "open")
    )
    open_alerts = open_alerts_result.scalar() or 0

    # Total alerts today
    alerts_today_result = await db.execute(
        select(func.count()).select_from(Alert).where(Alert.created_at >= today_start)
    )
    alerts_today = alerts_today_result.scalar() or 0

    # Rules count
    rules_result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(cast(CorrelationRule.enabled, Integer)).label("enabled"),
        ).select_from(CorrelationRule)
    )
    rules_row = rules_result.one()
    total_rules = rules_row.total or 0
    enabled_rules = int(rules_row.enabled or 0)

    # Top 5 source IPs
    top_ips_result = await db.execute(
        select(SecurityEvent.source_ip, func.count().label("count"))
        .where(SecurityEvent.source_ip.isnot(None))
        .where(SecurityEvent.timestamp >= today_start)
        .group_by(SecurityEvent.source_ip)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_ips = [{"ip": row.source_ip, "count": row.count} for row in top_ips_result.all()]

    # Severity breakdown (today)
    severity_result = await db.execute(
        select(SecurityEvent.severity, func.count().label("count"))
        .where(SecurityEvent.timestamp >= today_start)
        .group_by(SecurityEvent.severity)
    )
    severity_dist = {row.severity: row.count for row in severity_result.all()}

    # Critical events last 1h
    one_hour_ago = now - timedelta(hours=1)
    critical_1h_result = await db.execute(
        select(func.count())
        .select_from(SecurityEvent)
        .where(SecurityEvent.severity == "critical")
        .where(SecurityEvent.timestamp >= one_hour_ago)
    )
    critical_last_hour = critical_1h_result.scalar() or 0

    return {
        "events_today": events_today,
        "total_events": total_events,
        "open_alerts": open_alerts,
        "alerts_today": alerts_today,
        "critical_events_last_hour": critical_last_hour,
        "rules": {"total": total_rules, "enabled": enabled_rules, "disabled": total_rules - enabled_rules},
        "top_source_ips": top_ips,
        "severity_distribution_today": severity_dist,
        "generated_at": now.isoformat(),
    }


@router.get("/events-over-time", summary="Event counts bucketed by hour")
async def events_over_time(
    hours: int = Query(24, ge=1, le=168, description="Number of past hours to include"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns event counts per hour for the last N hours."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)

    # PostgreSQL date_trunc approach
    result = await db.execute(
        text(
            """
            SELECT
                date_trunc('hour', timestamp AT TIME ZONE 'UTC') AS hour,
                COUNT(*) AS count
            FROM security_events
            WHERE timestamp >= :since
            GROUP BY hour
            ORDER BY hour ASC
            """
        ),
        {"since": since},
    )
    rows = result.all()

    # Build complete hourly buckets (fill zeros for missing hours)
    buckets: dict[str, int] = {}
    for row in rows:
        if row.hour:
            key = row.hour.strftime("%Y-%m-%dT%H:00:00Z") if hasattr(row.hour, "strftime") else str(row.hour)
            buckets[key] = row.count

    # Fill in missing hours
    all_buckets = []
    for h in range(hours):
        bucket_time = (now - timedelta(hours=hours - h)).replace(minute=0, second=0, microsecond=0)
        key = bucket_time.strftime("%Y-%m-%dT%H:00:00Z")
        all_buckets.append({"hour": key, "count": buckets.get(key, 0)})

    return {
        "hours": hours,
        "since": since.isoformat(),
        "until": now.isoformat(),
        "buckets": all_buckets,
        "total": sum(b["count"] for b in all_buckets),
    }


@router.get("/top-sources", summary="Top source IPs by event count")
async def top_sources(
    limit: int = Query(10, ge=1, le=100),
    hours: int = Query(24, ge=1, le=720),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns the top source IPs sorted by event volume."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = (
        select(
            SecurityEvent.source_ip,
            func.count().label("count"),
            func.max(SecurityEvent.timestamp).label("last_seen"),
        )
        .where(SecurityEvent.source_ip.isnot(None))
        .where(SecurityEvent.timestamp >= since)
    )
    if severity:
        query = query.where(SecurityEvent.severity == severity)

    query = query.group_by(SecurityEvent.source_ip).order_by(func.count().desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return {
        "hours": hours,
        "limit": limit,
        "items": [
            {
                "source_ip": row.source_ip,
                "count": row.count,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in rows
        ],
    }


@router.get("/severity-distribution", summary="Event counts broken down by severity")
async def severity_distribution(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(SecurityEvent.severity, func.count().label("count"))
        .where(SecurityEvent.timestamp >= since)
        .group_by(SecurityEvent.severity)
        .order_by(func.count().desc())
    )
    rows = result.all()

    total = sum(row.count for row in rows)
    items = [
        {
            "severity": row.severity,
            "count": row.count,
            "percentage": round((row.count / total * 100), 1) if total > 0 else 0,
        }
        for row in rows
    ]

    return {"hours": hours, "total": total, "items": items}


@router.get("/category-distribution", summary="Event counts broken down by category")
async def category_distribution(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(SecurityEvent.category, func.count().label("count"))
        .where(SecurityEvent.timestamp >= since)
        .group_by(SecurityEvent.category)
        .order_by(func.count().desc())
    )
    rows = result.all()

    total = sum(row.count for row in rows)
    items = [
        {
            "category": row.category,
            "count": row.count,
            "percentage": round((row.count / total * 100), 1) if total > 0 else 0,
        }
        for row in rows
    ]

    return {"hours": hours, "total": total, "items": items}


@router.get("/geo-distribution", summary="Source event counts broken down by country")
async def geo_distribution(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(SecurityEvent.country, func.count().label("count"))
        .where(SecurityEvent.timestamp >= since)
        .where(SecurityEvent.country.isnot(None))
        .group_by(SecurityEvent.country)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = result.all()

    total_result = await db.execute(
        select(func.count())
        .select_from(SecurityEvent)
        .where(SecurityEvent.timestamp >= since)
        .where(SecurityEvent.country.isnot(None))
    )
    total = total_result.scalar() or 0

    items = [
        {
            "country": row.country,
            "count": row.count,
            "percentage": round((row.count / total * 100), 1) if total > 0 else 0,
        }
        for row in rows
    ]

    return {"hours": hours, "total": total, "items": items}


@router.get("/alert-trend", summary="Alert creation trend over time")
async def alert_trend(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        text(
            """
            SELECT
                date_trunc('hour', created_at AT TIME ZONE 'UTC') AS hour,
                severity,
                COUNT(*) AS count
            FROM alerts
            WHERE created_at >= :since
            GROUP BY hour, severity
            ORDER BY hour ASC
            """
        ),
        {"since": since},
    )
    rows = result.all()

    buckets: dict[str, dict] = {}
    for row in rows:
        if row.hour:
            key = row.hour.strftime("%Y-%m-%dT%H:00:00Z") if hasattr(row.hour, "strftime") else str(row.hour)
            if key not in buckets:
                buckets[key] = {}
            buckets[key][row.severity] = row.count

    timeline = []
    for h in range(hours):
        bucket_time = (now - timedelta(hours=hours - h)).replace(minute=0, second=0, microsecond=0)
        key = bucket_time.strftime("%Y-%m-%dT%H:00:00Z")
        severity_counts = buckets.get(key, {})
        timeline.append({
            "hour": key,
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
            "total": sum(severity_counts.values()),
        })

    return {"hours": hours, "since": since.isoformat(), "timeline": timeline}


@router.get("/dashboard", summary="Aggregated dashboard statistics")
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> dict:
    """Single endpoint returning all dashboard data.
    Queries run sequentially on the same AsyncSession to avoid
    concurrent-use errors (AsyncSession is not concurrency-safe)."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    one_hour_ago = now - timedelta(hours=1)
    since_24h = now - timedelta(hours=24)

    # --- Sequential scalar queries (safe for AsyncSession) ---
    events_today     = await db.scalar(select(func.count()).select_from(SecurityEvent).where(SecurityEvent.timestamp >= today_start)) or 0
    events_last_hour = await db.scalar(select(func.count()).select_from(SecurityEvent).where(SecurityEvent.timestamp >= one_hour_ago)) or 0
    open_alerts      = await db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "open")) or 0
    critical_alerts  = await db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "open", Alert.severity == "critical")) or 0
    high_alerts      = await db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "open", Alert.severity == "high")) or 0
    active_rules     = await db.scalar(select(func.count()).select_from(CorrelationRule).where(CorrelationRule.enabled.is_(True))) or 0
    threats_detected = await db.scalar(select(func.count()).select_from(ThreatIndicator)) or 0

    overview = {
        "total_events_today": events_today,
        "events_last_hour": events_last_hour,
        "open_alerts": open_alerts,
        "critical_alerts": critical_alerts,
        "high_alerts": high_alerts,
        "active_rules": active_rules,
        "threats_detected": threats_detected,
    }

    # --- Events over time (24h, per-severity per hour) ---
    eot_result = await db.execute(
        text("""
            SELECT
                date_trunc('hour', timestamp AT TIME ZONE 'UTC') AS hour,
                severity,
                COUNT(*) AS cnt
            FROM security_events
            WHERE timestamp >= :since
            GROUP BY hour, severity
            ORDER BY hour ASC
        """),
        {"since": since_24h},
    )
    eot_buckets: dict[str, dict] = {}
    for row in eot_result.all():
        if row.hour:
            key = row.hour.strftime("%Y-%m-%dT%H:00:00Z") if hasattr(row.hour, "strftime") else str(row.hour)
            if key not in eot_buckets:
                eot_buckets[key] = {}
            eot_buckets[key][row.severity] = row.cnt

    events_over_time = []
    for h in range(24):
        bucket_time = (now - timedelta(hours=24 - h)).replace(minute=0, second=0, microsecond=0)
        key = bucket_time.strftime("%Y-%m-%dT%H:00:00Z")
        sev = eot_buckets.get(key, {})
        events_over_time.append({
            "timestamp": key,
            "count": sum(sev.values()),
            "critical": sev.get("critical", 0),
            "high": sev.get("high", 0),
            "medium": sev.get("medium", 0),
            "low": sev.get("low", 0),
        })

    # --- Severity distribution (24h) ---
    sev_result = await db.execute(
        select(SecurityEvent.severity, func.count().label("count"))
        .where(SecurityEvent.timestamp >= since_24h)
        .group_by(SecurityEvent.severity)
        .order_by(func.count().desc())
    )
    severity_distribution = [{"severity": row.severity, "count": row.count} for row in sev_result.all()]

    # --- Category distribution (24h, top 10) ---
    cat_result = await db.execute(
        select(SecurityEvent.category, func.count().label("count"))
        .where(SecurityEvent.timestamp >= since_24h)
        .group_by(SecurityEvent.category)
        .order_by(func.count().desc())
        .limit(10)
    )
    category_distribution = [{"category": row.category, "count": row.count} for row in cat_result.all()]

    # --- Top sources (24h, top 10, with severity breakdown) ---
    top_src_result = await db.execute(
        text("""
            SELECT
                source_ip,
                COUNT(*) AS cnt,
                COUNT(*) FILTER (WHERE severity = 'critical') AS critical,
                COUNT(*) FILTER (WHERE severity = 'high') AS high,
                COUNT(*) FILTER (WHERE severity = 'medium') AS medium,
                COUNT(*) FILTER (WHERE severity = 'low') AS low
            FROM security_events
            WHERE source_ip IS NOT NULL AND timestamp >= :since
            GROUP BY source_ip
            ORDER BY cnt DESC
            LIMIT 10
        """),
        {"since": since_24h},
    )
    top_sources = [
        {
            "source_ip": row.source_ip,
            "count": row.cnt,
            "severity_breakdown": {
                "critical": row.critical,
                "high": row.high,
                "medium": row.medium,
                "low": row.low,
            },
        }
        for row in top_src_result.all()
    ]

    # --- Recent alerts (10 most recent) ---
    recent_result = await db.execute(
        select(Alert).order_by(Alert.created_at.desc()).limit(10)
    )
    recent_alerts = [
        {
            "id": str(a.id),
            "title": a.title,
            "description": a.description,
            "severity": a.severity,
            "status": a.status,
            "rule_id": str(a.rule_id) if a.rule_id else None,
            "rule_name": None,
            "event_ids": a.event_ids or [],
            "source_ips": a.source_ips or [],
            "affected_users": a.affected_users or [],
            "affected_hosts": [],
            "mitre_tactic": a.mitre_tactic,
            "mitre_technique": a.mitre_technique,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.created_at.isoformat(),
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            "assigned_to": a.assigned_to,
            "notes": a.notes,
            "false_positive_reason": None,
            "event_count": len(a.event_ids or []),
        }
        for a in recent_result.scalars().all()
    ]

    return {
        "overview": overview,
        "events_over_time": events_over_time,
        "severity_distribution": severity_distribution,
        "category_distribution": category_distribution,
        "top_sources": top_sources,
        "recent_alerts": recent_alerts,
    }
