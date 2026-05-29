"""
Correlation engine: evaluates events against rules and creates Alerts.
Uses an in-memory sliding-window counter for threshold-based rules.

IMPORTANT — Single-process assumption:
  WindowCounter state is held in a plain Python dict in this process.
  asyncio.Lock provides safe concurrency within a single event loop, but
  this does NOT work across multiple worker processes (e.g. gunicorn with
  workers > 1, or multiple uvicorn instances behind a load balancer).
  In a multi-process deployment the counters would be per-process and
  thresholds would never be reached correctly. For multi-process support,
  migrate _counters to a shared Redis backend (e.g. a sorted-set per
  window_key with ZADD + ZCOUNT + EXPIRE).
"""
import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.event import SecurityEvent
from app.models.rule import CorrelationRule
from app.services.risk_aggregation import risk_aggregation_service

logger = logging.getLogger(__name__)


class WindowCounter:
    """Sliding-window event tracker for a single (rule_id, group_key)."""

    def __init__(self, window_seconds: int):
        self.window_seconds = window_seconds
        self.events: list[tuple[float, str]] = []  # (timestamp_epoch, event_id)

    def add(self, event_id: str, ts: float) -> None:
        self.events.append((ts, event_id))
        self._purge(ts)

    def count(self, now: float) -> int:
        self._purge(now)
        return len(self.events)

    def event_ids(self) -> list[str]:
        return [eid for _, eid in self.events]

    def _purge(self, now: float) -> None:
        cutoff = now - self.window_seconds
        self.events = [(t, eid) for t, eid in self.events if t >= cutoff]


class CorrelationEngine:
    """Evaluates SecurityEvents against CorrelationRules and generates Alerts."""

    def __init__(self) -> None:
        self._rules: list[CorrelationRule] = []
        self._rules_loaded_at: datetime | None = None
        # counters[(rule_id, group_key)] -> WindowCounter
        # Plain dict — each counter is constructed explicitly with the rule's time_window.
        # NOTE: assumes single-process deployment (asyncio.Lock provides safe concurrency).
        self._counters: dict[tuple[str, str], WindowCounter] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    # -----------------------------------------------------------------------
    # Rule loading
    # -----------------------------------------------------------------------

    async def load_rules(self, db: AsyncSession) -> None:
        result = await db.execute(select(CorrelationRule).where(CorrelationRule.enabled == True))  # noqa: E712
        self._rules = list(result.scalars().all())
        self._rules_loaded_at = datetime.now(timezone.utc)
        logger.info("Loaded %d correlation rules", len(self._rules))

    async def reload_rules_if_stale(self, db: AsyncSession, max_age_seconds: int = 60) -> None:
        if self._rules_loaded_at is None:
            await self.load_rules(db)
            return
        age = (datetime.now(timezone.utc) - self._rules_loaded_at).total_seconds()
        if age > max_age_seconds:
            await self.load_rules(db)

    # -----------------------------------------------------------------------
    # Main evaluation
    # -----------------------------------------------------------------------

    async def evaluate_event(self, db: AsyncSession, event: SecurityEvent) -> list[Alert]:
        await self.reload_rules_if_stale(db)
        generated: list[Alert] = []

        for rule in self._rules:
            try:
                alert = await self._evaluate_rule(db, rule, event)
                if alert:
                    generated.append(alert)
            except Exception as exc:
                logger.error("Error evaluating rule %s: %s", rule.name, exc)

        return generated

    async def _evaluate_rule(
        self, db: AsyncSession, rule: CorrelationRule, event: SecurityEvent
    ) -> Alert | None:
        condition = rule.condition or {}
        if not self._matches_condition(event, condition):
            return None

        # Determine grouping key for threshold tracking
        group_by = condition.get("group_by", "source_ip")
        group_value = self._get_field(event, group_by) or "__all__"
        window_key = (str(rule.id), str(group_value))

        now = event.timestamp.timestamp() if event.timestamp else datetime.now(timezone.utc).timestamp()

        # FIX: perform counter add, threshold check, AND reset atomically under
        # a single lock acquisition to prevent duplicate alerts from concurrent
        # coroutines reading count > threshold before either resets the counter.
        threshold_met = False
        event_ids: list[str] = []
        count = 0

        async with self._lock:
            if window_key not in self._counters:
                self._counters[window_key] = WindowCounter(rule.time_window)
            counter = self._counters[window_key]
            # Safe to mutate window_seconds here — we hold the lock, so the
            # cleanup task (which also acquires self._lock) cannot be mid-purge.
            counter.window_seconds = rule.time_window
            counter.add(str(event.id), now)
            count = counter.count(now)
            if count >= rule.threshold:
                threshold_met = True
                event_ids = counter.event_ids()
                # Reset immediately so the next window starts fresh and we
                # don't fire a duplicate alert before the window expires.
                self._counters[window_key] = WindowCounter(rule.time_window)

        if not threshold_met:
            return None

        alert = await self._create_alert(db, rule, event, count, event_ids, str(group_value))
        return alert

    # -----------------------------------------------------------------------
    # Condition matching
    # -----------------------------------------------------------------------

    def _matches_condition(self, event: SecurityEvent, condition: dict) -> bool:
        """Evaluate a condition dict against an event."""
        op = condition.get("operator", "AND").upper()
        filters = condition.get("filters", [])

        # Simple single-condition format: {"field": ..., "op": ..., "value": ...}
        if "field" in condition:
            return self._eval_filter(event, condition)

        if not filters:
            return True

        results = [self._eval_filter(event, f) for f in filters]
        if op == "AND":
            return all(results)
        if op == "OR":
            return any(results)
        return False

    def _eval_filter(self, event: SecurityEvent, flt: dict) -> bool:
        field = flt.get("field", "")
        op = flt.get("op", "equals")
        value = flt.get("value")
        negate = flt.get("negate", False)

        event_value = self._get_field(event, field)

        if op == "equals":
            result = str(event_value).lower() == str(value).lower() if event_value is not None else False
        elif op == "not_equals":
            result = str(event_value).lower() != str(value).lower() if event_value is not None else True
        elif op == "contains":
            result = value.lower() in str(event_value).lower() if event_value is not None else False
        elif op == "not_contains":
            result = value.lower() not in str(event_value).lower() if event_value is not None else True
        elif op == "regex":
            result = bool(re.search(value, str(event_value), re.IGNORECASE)) if event_value is not None else False
        elif op == "in":
            result = str(event_value).lower() in [str(v).lower() for v in (value or [])]
        elif op == "not_in":
            result = str(event_value).lower() not in [str(v).lower() for v in (value or [])]
        elif op == "exists":
            result = event_value is not None
        elif op == "gt":
            try:
                result = float(str(event_value)) > float(str(value))
            except (ValueError, TypeError):
                result = False
        elif op == "lt":
            try:
                result = float(str(event_value)) < float(str(value))
            except (ValueError, TypeError):
                result = False
        else:
            result = False

        return not result if negate else result

    def _get_field(self, event: SecurityEvent, field: str) -> Any:
        """Get a field value from the event, supporting dot notation for parsed_fields."""
        if "." in field:
            parts = field.split(".", 1)
            if parts[0] == "parsed_fields" and event.parsed_fields:
                return event.parsed_fields.get(parts[1])
        return getattr(event, field, None)

    # -----------------------------------------------------------------------
    # Alert creation
    # -----------------------------------------------------------------------

    async def _create_alert(
        self,
        db: AsyncSession,
        rule: CorrelationRule,
        event: SecurityEvent,
        count: int,
        event_ids: list[str],
        group_value: str,
    ) -> Alert:
        """
        Create or update a correlation Alert for a rule-triggering event, using a deduplication key based on the rule and group.
        
        If an open (not `resolved` or `false_positive`) alert exists with the deduplication key `"{rule.id}:{group_value}"`, increment its `hit_count`, merge new `event_ids` (avoiding duplicates), recompute its `risk_score`, update rule trigger statistics, persist changes, and return the existing alert. If no such alert exists, create a new `Alert` populated from the rule and event, compute its `risk_score`, update rule trigger statistics, persist the new alert, and return it.
        
        Parameters:
            db (AsyncSession): Database session used to query and persist alerts and rule state.
            rule (CorrelationRule): The correlation rule that triggered.
            event (SecurityEvent): The event that caused the rule to trigger.
            count (int): Number of matching events in the rule's time window.
            event_ids (list[str]): IDs of events contributing to the threshold being met.
            group_value (str): The grouping value used for deduplication (e.g., source IP or "__all__").
        
        Returns:
            Alert: The existing deduplicated alert updated, or the newly created alert.
        """
        title = rule.alert_title_template.format(
            rule_name=rule.name,
            count=count,
            window=rule.time_window,
            group=group_value,
        )
        description = rule.alert_description_template.format(
            rule_name=rule.name,
            count=count,
            window=rule.time_window,
            group=group_value,
        )

        source_ips = [str(event.source_ip)] if event.source_ip else []
        affected_users = [str(event.user)] if event.user else []

        # Compute dedup key for this (rule, group) combination
        dedup_key = f"{rule.id}:{group_value}"

        # Check for existing non-resolved/non-fp alert with same dedup key
        existing_result = await db.execute(
            select(Alert).where(
                Alert.dedup_key == dedup_key,
                Alert.status.notin_(["resolved", "false_positive"]),
            ).limit(1)
        )
        existing_alert = existing_result.scalar_one_or_none()

        if existing_alert is not None:
            # Increment hit_count and recalculate risk_score
            existing_alert.hit_count = (existing_alert.hit_count or 1) + 1
            # Merge new event IDs
            existing_ids = list(existing_alert.event_ids or [])
            for eid in event_ids:
                if eid not in existing_ids:
                    existing_ids.append(eid)
            existing_alert.event_ids = existing_ids
            existing_alert.risk_score = risk_aggregation_service.compute_alert_risk_score(existing_alert)
            db.add(existing_alert)

            # Update rule statistics
            rule.last_triggered = datetime.now(timezone.utc)
            rule.trigger_count = (rule.trigger_count or 0) + 1
            db.add(rule)

            await db.flush()
            logger.info(
                "Deduped alert '%s' (hit_count=%d) from rule '%s'",
                existing_alert.title, existing_alert.hit_count, rule.name,
            )
            return existing_alert

        alert = Alert(
            id=uuid.uuid4(),
            title=title,
            description=description,
            severity=rule.severity,
            status="open",
            rule_id=rule.id,
            event_ids=event_ids,
            source_ips=source_ips,
            affected_users=affected_users,
            mitre_tactic=rule.mitre_tactic,
            mitre_technique=rule.mitre_technique,
            hit_count=1,
            dedup_key=dedup_key,
        )
        alert.risk_score = risk_aggregation_service.compute_alert_risk_score(alert)
        db.add(alert)

        # Update rule statistics
        rule.last_triggered = datetime.now(timezone.utc)
        rule.trigger_count = (rule.trigger_count or 0) + 1
        db.add(rule)

        await db.flush()
        logger.info("Created alert '%s' from rule '%s'", title, rule.name)

        return alert

    # -----------------------------------------------------------------------
    # Maintenance
    # -----------------------------------------------------------------------

    async def start_cleanup_task(self, interval_seconds: int = 60) -> None:
        async def _cleanup_loop():
            while True:
                await asyncio.sleep(interval_seconds)
                await self._purge_old_counters()

        self._cleanup_task = asyncio.create_task(_cleanup_loop())
        logger.info("Started correlation engine cleanup task (interval=%ds)", interval_seconds)

    async def _purge_old_counters(self) -> None:
        now = datetime.now(timezone.utc).timestamp()
        async with self._lock:
            to_delete = [
                k for k, v in self._counters.items()
                if v.count(now) == 0
            ]
            for k in to_delete:
                del self._counters[k]
        if to_delete:
            logger.debug("Purged %d empty window counters", len(to_delete))

    def stop_cleanup_task(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()


# ---------------------------------------------------------------------------
# Default built-in rules (seeded on startup)
# ---------------------------------------------------------------------------

DEFAULT_RULES: list[dict] = [
    {
        "name": "SSH Brute Force Detection",
        "description": "Detects more than 5 failed SSH authentication attempts from the same IP within 5 minutes.",
        "enabled": True,
        "severity": "high",
        "category": "authentication",
        "condition": {
            "operator": "AND",
            "group_by": "source_ip",
            "filters": [
                {"field": "log_type", "op": "equals", "value": "ssh"},
                {"field": "action", "op": "equals", "value": "failed"},
            ],
        },
        "threshold": 5,
        "time_window": 300,
        "mitre_tactic": "Credential Access",
        "mitre_technique": "T1110.001",
        "alert_title_template": "SSH Brute Force from {group}",
        "alert_description_template": (
            "Detected {count} failed SSH login attempts from {group} "
            "within {window} seconds. Possible brute force attack."
        ),
        "tags": ["ssh", "brute-force", "authentication"],
    },
    {
        "name": "Port Scan Detection",
        "description": "Detects connections to more than 20 distinct destination ports from the same IP within 1 minute.",
        "enabled": True,
        "severity": "medium",
        "category": "network",
        "condition": {
            "operator": "AND",
            "group_by": "source_ip",
            "filters": [
                {"field": "log_type", "op": "equals", "value": "firewall"},
                {"field": "category", "op": "equals", "value": "network"},
            ],
        },
        "threshold": 20,
        "time_window": 60,
        "mitre_tactic": "Discovery",
        "mitre_technique": "T1046",
        "alert_title_template": "Port Scan Detected from {group}",
        "alert_description_template": (
            "Detected {count} firewall events from {group} within {window} seconds. "
            "Possible network port scan activity."
        ),
        "tags": ["port-scan", "network", "discovery"],
    },
    {
        "name": "Multiple Failed Logins Same User",
        "description": "Detects more than 3 failed login attempts for the same user within 10 minutes.",
        "enabled": True,
        "severity": "medium",
        "category": "authentication",
        "condition": {
            "operator": "AND",
            "group_by": "user",
            "filters": [
                {"field": "category", "op": "equals", "value": "authentication"},
                {"field": "action", "op": "equals", "value": "failed"},
            ],
        },
        "threshold": 3,
        "time_window": 600,
        "mitre_tactic": "Credential Access",
        "mitre_technique": "T1110",
        "alert_title_template": "Multiple Failed Logins for user {group}",
        "alert_description_template": (
            "User {group} has {count} failed login attempts within {window} seconds."
        ),
        "tags": ["failed-login", "authentication", "credential-access"],
    },
    {
        "name": "Privilege Escalation via Sudo",
        "description": "Detects any sudo command run as root.",
        "enabled": True,
        "severity": "high",
        "category": "system",
        "condition": {
            "operator": "AND",
            "group_by": "user",
            "filters": [
                {"field": "log_type", "op": "equals", "value": "sudo"},
                {"field": "parsed_fields.run_as", "op": "equals", "value": "root"},
            ],
        },
        "threshold": 1,
        "time_window": 3600,
        "mitre_tactic": "Privilege Escalation",
        "mitre_technique": "T1548.003",
        "alert_title_template": "Privilege Escalation via sudo by {group}",
        "alert_description_template": (
            "User {group} executed a command as root via sudo. "
            "This was detected {count} times in {window} seconds."
        ),
        "tags": ["sudo", "privilege-escalation", "root"],
    },
    {
        "name": "Traffic to Known Malicious IP",
        "description": "Detects network connections to IPs tagged as threat indicators.",
        "enabled": True,
        "severity": "critical",
        "category": "threat",
        "condition": {
            "operator": "AND",
            "group_by": "source_ip",
            "filters": [
                {"field": "tags", "op": "contains", "value": "threat-match"},
            ],
        },
        "threshold": 1,
        "time_window": 86400,
        "mitre_tactic": "Command and Control",
        "mitre_technique": "T1071",
        "alert_title_template": "Malware C2 Traffic Detected from {group}",
        "alert_description_template": (
            "Network traffic involving a known malicious indicator was detected "
            "{count} times from {group} in the last {window} seconds."
        ),
        "tags": ["threat-intel", "c2", "malware"],
    },
]


async def seed_default_rules(db: AsyncSession) -> None:
    """Insert default rules if they don't already exist."""
    for rule_data in DEFAULT_RULES:
        existing = await db.execute(
            select(CorrelationRule).where(CorrelationRule.name == rule_data["name"])
        )
        if existing.scalar_one_or_none() is None:
            rule = CorrelationRule(
                id=uuid.uuid4(),
                **rule_data,
            )
            db.add(rule)
            logger.info("Seeded default rule: %s", rule_data["name"])
    await db.commit()
    logger.info("Default rule seeding complete.")


# Module-level singleton
correlation_engine = CorrelationEngine()
