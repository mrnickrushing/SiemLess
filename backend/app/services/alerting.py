"""
Alert notification service: sends alerts via email, Slack, or generic webhook.
"""
import asyncio
import json
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from app.config import settings
from app.models.alert import Alert
from app.models.rule import CorrelationRule

logger = logging.getLogger(__name__)


def _format_alert_dict(alert: Alert, rule: Optional[CorrelationRule] = None) -> dict:
    """Return a structured dict representation of an alert for notifications."""
    return {
        "id": str(alert.id),
        "title": alert.title,
        "description": alert.description,
        "severity": alert.severity,
        "status": alert.status,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "rule_name": rule.name if rule else None,
        "source_ips": alert.source_ips or [],
        "affected_users": alert.affected_users or [],
        "mitre_tactic": alert.mitre_tactic,
        "mitre_technique": alert.mitre_technique,
        "event_count": len(alert.event_ids or []),
    }


class AlertService:
    """Handles dispatching alert notifications to configured channels."""

    def __init__(self) -> None:
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def send_alert(self, alert: Alert, rule: Optional[CorrelationRule] = None) -> None:
        """Dispatch alert notifications concurrently to all configured channels."""
        tasks = []

        if settings.ALERT_EMAIL and settings.SMTP_HOST:
            tasks.append(self.send_email(alert, rule))

        if settings.SLACK_WEBHOOK_URL:
            tasks.append(self.send_slack(alert, rule))

        if settings.ALERT_WEBHOOK_URL:
            tasks.append(self.send_webhook(alert, rule))

        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                channel = ["email", "slack", "webhook"][i] if i < 3 else f"channel[{i}]"
                logger.error("Failed to send %s alert for alert %s: %s", channel, alert.id, res)

    async def send_email(self, alert: Alert, rule: Optional[CorrelationRule] = None) -> None:
        """Send alert via SMTP email."""
        if not settings.SMTP_HOST or not settings.ALERT_EMAIL:
            logger.debug("Email alerting not configured")
            return

        severity_emoji = {
            "critical": "[CRITICAL]",
            "high": "[HIGH]",
            "medium": "[MEDIUM]",
            "low": "[LOW]",
        }.get(alert.severity, "[INFO]")

        subject = f"SiemLess Alert {severity_emoji}: {alert.title}"

        alert_data = _format_alert_dict(alert, rule)
        body_text = self._format_email_text(alert_data)
        body_html = self._format_email_html(alert_data)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER or "siemless@localhost"
        msg["To"] = settings.ALERT_EMAIL

        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        try:
            if settings.SMTP_TLS:
                context = ssl.create_default_context()
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    if settings.SMTP_USER and settings.SMTP_PASS:
                        server.login(settings.SMTP_USER, settings.SMTP_PASS)
                    server.sendmail(msg["From"], settings.ALERT_EMAIL, msg.as_string())
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    if settings.SMTP_USER and settings.SMTP_PASS:
                        server.login(settings.SMTP_USER, settings.SMTP_PASS)
                    server.sendmail(msg["From"], settings.ALERT_EMAIL, msg.as_string())

            logger.info("Email alert sent for alert %s", alert.id)
        except Exception as exc:
            logger.error("SMTP error sending alert %s: %s", alert.id, exc)
            raise

    async def send_slack(self, alert: Alert, rule: Optional[CorrelationRule] = None) -> None:
        """Send alert to Slack via incoming webhook."""
        if not settings.SLACK_WEBHOOK_URL:
            return

        severity_color = {
            "critical": "#FF0000",
            "high": "#FF6600",
            "medium": "#FFCC00",
            "low": "#36A64F",
        }.get(alert.severity, "#808080")

        alert_data = _format_alert_dict(alert, rule)

        payload = {
            "attachments": [
                {
                    "color": severity_color,
                    "title": f":rotating_light: {alert.title}",
                    "text": alert.description or "",
                    "fields": [
                        {"title": "Severity", "value": alert.severity.upper(), "short": True},
                        {"title": "Status", "value": alert.status, "short": True},
                        {"title": "Rule", "value": rule.name if rule else "Manual", "short": True},
                        {"title": "Alert ID", "value": str(alert.id), "short": True},
                        {
                            "title": "Source IPs",
                            "value": ", ".join(alert_data["source_ips"]) or "N/A",
                            "short": False,
                        },
                        {
                            "title": "Affected Users",
                            "value": ", ".join(alert_data["affected_users"]) or "N/A",
                            "short": False,
                        },
                    ],
                    "footer": "SiemLess SIEM",
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                }
            ]
        }

        if alert.mitre_tactic:
            payload["attachments"][0]["fields"].append(
                {"title": "MITRE Tactic", "value": alert.mitre_tactic, "short": True}
            )
        if alert.mitre_technique:
            payload["attachments"][0]["fields"].append(
                {"title": "MITRE Technique", "value": alert.mitre_technique, "short": True}
            )

        resp = await self.http.post(settings.SLACK_WEBHOOK_URL, json=payload)
        resp.raise_for_status()
        logger.info("Slack alert sent for alert %s", alert.id)

    async def send_webhook(self, alert: Alert, rule: Optional[CorrelationRule] = None) -> None:
        """Send alert as a generic JSON POST webhook."""
        if not settings.ALERT_WEBHOOK_URL:
            return

        payload = {
            "event": "alert.created",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": _format_alert_dict(alert, rule),
        }

        resp = await self.http.post(
            settings.ALERT_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json", "X-Source": "siemless"},
        )
        resp.raise_for_status()
        logger.info("Webhook alert sent for alert %s", alert.id)

    # -----------------------------------------------------------------------
    # Formatting helpers
    # -----------------------------------------------------------------------

    def _format_email_text(self, alert_data: dict) -> str:
        lines = [
            "SiemLess Security Alert",
            "=" * 40,
            f"Title:       {alert_data['title']}",
            f"Severity:    {alert_data['severity'].upper()}",
            f"Status:      {alert_data['status']}",
            f"Created:     {alert_data['created_at']}",
            f"Rule:        {alert_data['rule_name'] or 'N/A'}",
            f"Alert ID:    {alert_data['id']}",
            "",
            "Description:",
            alert_data.get("description") or "No description provided.",
            "",
            f"Source IPs:      {', '.join(alert_data['source_ips']) or 'N/A'}",
            f"Affected Users:  {', '.join(alert_data['affected_users']) or 'N/A'}",
            f"Events Count:    {alert_data['event_count']}",
        ]
        if alert_data.get("mitre_tactic"):
            lines.append(f"MITRE Tactic:    {alert_data['mitre_tactic']}")
        if alert_data.get("mitre_technique"):
            lines.append(f"MITRE Technique: {alert_data['mitre_technique']}")
        return "\n".join(lines)

    def _format_email_html(self, alert_data: dict) -> str:
        severity_colors = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#28a745",
        }
        color = severity_colors.get(alert_data["severity"], "#6c757d")

        return f"""
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background:{color}; color:white; padding:15px; border-radius:4px 4px 0 0;">
    <h2 style="margin:0;">SiemLess Security Alert</h2>
    <p style="margin:5px 0 0 0; font-size:1.2em;">{alert_data['title']}</p>
  </div>
  <div style="border:1px solid #ddd; border-top:none; padding:15px; border-radius:0 0 4px 4px;">
    <table style="width:100%; border-collapse:collapse;">
      <tr><td style="padding:5px; font-weight:bold; width:140px;">Severity</td>
          <td style="padding:5px;"><span style="background:{color};color:white;padding:2px 8px;border-radius:3px;">{alert_data['severity'].upper()}</span></td></tr>
      <tr><td style="padding:5px; font-weight:bold;">Status</td><td style="padding:5px;">{alert_data['status']}</td></tr>
      <tr><td style="padding:5px; font-weight:bold;">Rule</td><td style="padding:5px;">{alert_data['rule_name'] or 'N/A'}</td></tr>
      <tr><td style="padding:5px; font-weight:bold;">Created</td><td style="padding:5px;">{alert_data['created_at']}</td></tr>
      <tr><td style="padding:5px; font-weight:bold;">Alert ID</td><td style="padding:5px; font-size:0.85em; color:#666;">{alert_data['id']}</td></tr>
      <tr><td style="padding:5px; font-weight:bold;">Events</td><td style="padding:5px;">{alert_data['event_count']}</td></tr>
      <tr><td style="padding:5px; font-weight:bold;">Source IPs</td><td style="padding:5px;">{', '.join(alert_data['source_ips']) or 'N/A'}</td></tr>
      <tr><td style="padding:5px; font-weight:bold;">Users</td><td style="padding:5px;">{', '.join(alert_data['affected_users']) or 'N/A'}</td></tr>
    </table>
    <hr style="margin:15px 0; border:none; border-top:1px solid #eee;">
    <p style="color:#555;">{alert_data.get('description') or 'No description provided.'}</p>
    <hr style="margin:15px 0; border:none; border-top:1px solid #eee;">
    <p style="color:#999; font-size:0.8em;">This alert was generated by SiemLess SIEM.</p>
  </div>
</body></html>
"""


# Module-level singleton
alert_service = AlertService()
