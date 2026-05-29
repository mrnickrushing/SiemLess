"""SOAR Playbook execution engine."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.alert import Alert
from app.models.soar import Playbook, PlaybookRun

logger = logging.getLogger(__name__)


class PlaybookEngine:

    async def evaluate_alert(self, db: AsyncSession, alert: Alert) -> None:
        """Find matching playbooks for this alert and execute them as background tasks."""
        try:
            playbooks = await self._find_matching_playbooks(db, alert)
            for playbook in playbooks:
                asyncio.create_task(
                    self._execute(playbook.id, str(alert.id), "system")
                )
        except Exception as exc:
            logger.warning("Playbook evaluation failed: %s", exc)

    async def _find_matching_playbooks(
        self, db: AsyncSession, alert: Alert
    ) -> list[Playbook]:
        result = await db.execute(
            select(Playbook).where(Playbook.enabled == True)  # noqa: E712
        )
        playbooks = result.scalars().all()
        matching = []
        for pb in playbooks:
            if self._matches_trigger(pb, alert):
                matching.append(pb)
        return matching

    def _matches_trigger(self, playbook: Playbook, alert: Alert) -> bool:
        trigger_type = playbook.trigger_type
        config = playbook.trigger_config or {}

        if trigger_type == "manual":
            return False
        if trigger_type == "alert_severity":
            return alert.severity == config.get("severity")
        if trigger_type == "alert_rule":
            return str(alert.rule_id) == str(config.get("rule_id", ""))
        return False

    async def _execute(
        self,
        playbook_id: str,
        alert_id: Optional[str],
        triggered_by: str,
    ) -> None:
        async with AsyncSessionLocal() as db:
            pb_result = await db.execute(
                select(Playbook).where(Playbook.id == playbook_id)
            )
            playbook = pb_result.scalar_one_or_none()
            if not playbook:
                return

            run = PlaybookRun(
                id=str(uuid.uuid4()),
                playbook_id=playbook_id,
                alert_id=alert_id,
                triggered_by=triggered_by,
                started_at=datetime.now(timezone.utc),
                status="running",
            )
            db.add(run)
            await db.flush()

            step_results = []
            steps = playbook.steps or []

            # Fetch alert for context
            alert = None
            if alert_id:
                alert_result = await db.execute(
                    select(Alert).where(Alert.id == alert_id)
                )
                alert = alert_result.scalar_one_or_none()

            for step in steps:
                action = step.get("action", "")
                params = step.get("params", {})
                try:
                    output = await self._dispatch_action(db, action, alert, params)
                    step_results.append({
                        "action": action,
                        "success": True,
                        "output": output,
                    })
                except Exception as exc:
                    step_results.append({
                        "action": action,
                        "success": False,
                        "error": str(exc),
                    })
                    if step.get("stop_on_failure", True):
                        run.status = "failed"
                        run.error_message = str(exc)[:500]
                        break
            else:
                run.status = "completed"

            run.step_results = step_results
            run.finished_at = datetime.now(timezone.utc)

            # Update playbook stats
            playbook.run_count = (playbook.run_count or 0) + 1
            playbook.last_triggered_at = datetime.now(timezone.utc)

            await db.commit()
            logger.info(
                "Playbook '%s' run %s: %s", playbook.name, run.id, run.status
            )

    async def _dispatch_action(
        self,
        db: AsyncSession,
        action: str,
        alert: Optional[Alert],
        params: dict,
    ) -> Any:
        handlers = {
            "send_webhook": self._action_webhook,
            "update_alert_status": self._action_update_alert,
            "create_case": self._action_create_case,
            "create_ticket": self._action_create_ticket,
            "add_to_watchlist": self._action_add_watchlist,
            "send_email": self._action_send_email,
        }
        handler = handlers.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action!r}")
        return await handler(db, alert, params)

    async def _action_webhook(
        self, db: AsyncSession, alert: Optional[Alert], params: dict
    ) -> dict:
        url = params.get("url")
        if not url:
            raise ValueError("webhook action requires 'url' param")
        payload = dict(params.get("payload", {}))
        if alert:
            payload["alert_id"] = str(alert.id)
            payload["alert_title"] = alert.title
            payload["alert_severity"] = alert.severity
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
        return {"status_code": resp.status_code}

    async def _action_update_alert(
        self, db: AsyncSession, alert: Optional[Alert], params: dict
    ) -> dict:
        if not alert:
            raise ValueError("No alert context")
        new_status = params.get("status")
        if new_status:
            alert.status = new_status
            await db.flush()
        return {"status": alert.status}

    async def _action_create_case(
        self, db: AsyncSession, alert: Optional[Alert], params: dict
    ) -> dict:
        from app.models.case import Case
        import uuid as _uuid
        title = params.get("title", f"Case for alert {str(alert.id)[:8] if alert else 'unknown'}")
        case = Case(
            id=str(_uuid.uuid4()),
            title=title,
            description=params.get("description", "Created by playbook"),
            severity=params.get("severity", "medium"),
            created_by="playbook",
        )
        db.add(case)
        await db.flush()
        return {"case_id": case.id}

    async def _action_create_ticket(
        self, db: AsyncSession, alert: Optional[Alert], params: dict
    ) -> dict:
        from app.services.integrations.manager import integration_manager
        integration_id = params.get("integration_id")
        if not integration_id:
            raise ValueError("create_ticket requires 'integration_id' param")
        title = params.get("title", f"Alert: {alert.title if alert else 'unknown'}")
        description = params.get("description", "")
        ticket_id = await integration_manager.create_ticket(
            db=db,
            integration_id=integration_id,
            title=title,
            description=description,
            priority=params.get("priority", "Medium"),
        )
        return {"ticket_id": ticket_id}

    async def _action_add_watchlist(
        self, db: AsyncSession, alert: Optional[Alert], params: dict
    ) -> dict:
        from app.models.watchlist import WatchlistEntry
        import uuid as _uuid
        entry_type = params.get("type", "ip")
        value = params.get("value") or (
            alert.source_ips[0] if alert and alert.source_ips else None
        )
        if not value:
            raise ValueError("No value for watchlist entry")
        entry = WatchlistEntry(
            id=_uuid.uuid4(),
            entry_type=entry_type,
            value=value,
            label=params.get("label", "Added by playbook"),
        )
        db.add(entry)
        await db.flush()
        return {"watchlist_entry_id": str(entry.id)}

    async def _action_send_email(
        self, db: AsyncSession, alert: Optional[Alert], params: dict
    ) -> dict:
        # Stub — real implementation would use the alerting service
        logger.info("Playbook send_email action (stub): to=%s", params.get("to"))
        return {"sent": True, "to": params.get("to")}

    async def trigger_manual(
        self, db: AsyncSession, playbook_id: str, alert_id: Optional[str], triggered_by: str
    ) -> str:
        """Manually trigger a playbook execution. Returns run ID."""
        result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Playbook {playbook_id} not found")

        run_id = str(uuid.uuid4())
        asyncio.create_task(self._execute(playbook_id, alert_id, triggered_by))
        return run_id


playbook_engine = PlaybookEngine()
