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
        """
        Evaluate an alert against enabled playbooks and schedule each matching playbook to run in the background.
        
        Exceptions raised while finding matches or scheduling executions are caught and logged and will not be propagated.
        """
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
        """
        Finds enabled playbooks whose trigger matches the given alert.
        
        Parameters:
            alert (Alert): Alert used to evaluate playbook trigger conditions.
        
        Returns:
            matching_playbooks (list[Playbook]): Enabled playbooks that match the alert's trigger configuration.
        """
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
        """
        Determine whether the playbook's trigger configuration matches the supplied alert.
        
        Checks the playbook's trigger_type and trigger_config:
        - "manual": never matches.
        - "alert_severity": matches when alert.severity equals config["severity"].
        - "alert_rule": matches when str(alert.rule_id) equals str(config["rule_id"]).
        
        Parameters:
            playbook (Playbook): Playbook containing trigger_type and trigger_config.
            alert (Alert): Alert to evaluate against the playbook trigger.
        
        Returns:
            bool: `true` if the playbook should be triggered for the alert, `false` otherwise.
        """
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
        run_id: Optional[str] = None,
    ) -> None:
        """
        Execute a playbook run: create a run record, execute each step's action, record step results, and update playbook metadata.
        
        Parameters:
            playbook_id (str): ID of the playbook to execute.
            alert_id (Optional[str]): ID of the alert providing context for actions; when None, actions execute without alert context.
            triggered_by (str): Identifier of the actor that triggered the run (e.g., "system" or a username).
            run_id (Optional[str]): Optional ID to use for the PlaybookRun; a new UUID is generated when omitted.
        
        Description:
            Loads the playbook and, if present, the alert; creates a PlaybookRun with status "running"; iterates through the playbook's steps dispatching each action and collecting per-step results. On action failure, records the error and, if the step's `stop_on_failure` is truthy (defaults to true), marks the run as "failed", stores a truncated error message (up to 500 chars), and stops further steps. If all steps complete without triggering a stop, marks the run as "completed". After execution, stores step results and finished timestamp, increments the playbook's run count, updates its last-triggered timestamp, commits the database transaction, and logs the run outcome.
        
        Behavior notes:
            - If the playbook with `playbook_id` does not exist, the function returns early without creating a run.
            - The function persists PlaybookRun, updated playbook fields, and any DB-side effects produced by action handlers.
        """
        async with AsyncSessionLocal() as db:
            pb_result = await db.execute(
                select(Playbook).where(Playbook.id == playbook_id)
            )
            playbook = pb_result.scalar_one_or_none()
            if not playbook:
                return

            run = PlaybookRun(
                id=run_id or str(uuid.uuid4()),
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
        """
        Dispatches a playbook action to the corresponding handler and returns the handler's result.
        
        Valid actions: "send_webhook", "update_alert_status", "create_case", "create_ticket", "add_to_watchlist", "send_email".
        
        Parameters:
            action (str): Action name to execute.
            params (dict): Parameters passed to the action handler.
            alert (Optional[Alert]): Optional alert context provided to the handler.
        
        Returns:
            Any: The value returned by the selected action handler.
        
        Raises:
            ValueError: If `action` is not one of the supported action names.
        """
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
        """
        Send a JSON webhook POST to the configured URL, optionally including alert context.
        
        Parameters:
            alert (Optional[Alert]): Alert whose `id`, `title`, and `severity` will be added to the payload when provided.
            params (dict): Action parameters. Must include `"url"` (the webhook endpoint). May include `"payload"` (a dict) whose keys are merged into the POST body.
        
        Returns:
            dict: A dictionary with `status_code` (int) from the HTTP response.
        
        Raises:
            ValueError: If `params` does not contain a `"url"` entry.
        """
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
        """
        Update the given alert's status when a new status is provided in params.
        
        Parameters:
        	alert (Optional[Alert]): The alert to update; must be provided or a ValueError is raised.
        	params (dict): Parameters for the action; may include `"status"` with the new alert status.
        
        Returns:
        	dict: `{"status": current_alert_status}` where `current_alert_status` is the alert's status after applying the update.
        
        Raises:
        	ValueError: If `alert` is None.
        """
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
        """
        Create a new Case record and return its identifier.
        
        Parameters:
            db (AsyncSession): Database session (used to persist the Case).
            alert (Optional[Alert]): Optional alert used to generate a default title when `params['title']` is not provided.
            params (dict): Creation options:
                - title (str, optional): Case title. Defaults to "Case for alert <alert-id-prefix>" when `alert` is present, otherwise "Case for alert unknown".
                - description (str, optional): Case description. Defaults to "Created by playbook".
                - severity (str, optional): Case severity. Defaults to "medium".
        
        Returns:
            dict: {"case_id": "<new-case-id>"} containing the created Case's id.
        """
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
        """
        Create a ticket in an external integration using the provided parameters.
        
        Parameters:
            alert (Optional[Alert]): Optional alert context used to derive a default title when `params['title']` is not provided.
            params (dict): Parameters for ticket creation. Expected keys:
                - integration_id (str): Required. ID of the integration to use.
                - title (str, optional): Ticket title; defaults to "Alert: <alert.title>" or "Alert: unknown".
                - description (str, optional): Ticket description; defaults to an empty string.
                - priority (str, optional): Ticket priority; defaults to "Medium".
        
        Returns:
            dict: A mapping containing the created ticket id as `{"ticket_id": <id>}`.
        
        Raises:
            ValueError: If `integration_id` is missing from `params`.
        """
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
        """
        Create and persist a watchlist entry using the provided params or, if missing, the alert context.
        
        Parameters:
            alert (Optional[Alert]): Optional alert used as a fallback to derive the entry value from alert.source_ips.
            params (dict): Configuration for the entry. Recognized keys:
                - "type" (str): Entry type, defaults to "ip".
                - "value" (str): Value to add to the watchlist; if omitted the first value from alert.source_ips is used when available.
                - "label" (str): Human-readable label for the entry, defaults to "Added by playbook".
        
        Returns:
            dict: {"watchlist_entry_id": "<uuid>"} containing the created watchlist entry id as a string.
        
        Raises:
            ValueError: If no value for the watchlist entry can be determined.
        """
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
        """
        Send an email based on the provided playbook parameters (stub implementation).
        
        Parameters:
            alert (Optional[Alert]): Optional alert context that can be used to populate message fields.
            params (dict): Action parameters; commonly includes `to` (recipient email), and may include `subject` and `body`.
        
        Returns:
            dict: Result object with `sent` indicating success (`True` in this stub) and `to` containing the recipient address.
        """
        logger.info("Playbook send_email action (stub): to=%s", params.get("to"))
        return {"sent": True, "to": params.get("to")}

    async def trigger_manual(
        self, db: AsyncSession, playbook_id: str, alert_id: Optional[str], triggered_by: str
    ) -> str:
        """
        Start a background execution of the specified playbook and return the generated run id.
        
        Parameters:
            playbook_id (str): ID of the playbook to execute.
            alert_id (Optional[str]): Optional alert ID to provide context for the run.
            triggered_by (str): Identifier of the actor that triggered the run.
        
        Returns:
            run_id (str): Generated UUID string that identifies the scheduled playbook run.
        
        Raises:
            ValueError: If no playbook exists with the given `playbook_id`.
        """
        result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Playbook {playbook_id} not found")

        run_id = str(uuid.uuid4())
        asyncio.create_task(self._execute(playbook_id, alert_id, triggered_by, run_id=run_id))
        return run_id


playbook_engine = PlaybookEngine()
