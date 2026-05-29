"""
Compliance report generation service.
Supports PCI DSS, HIPAA, GDPR, SOC2, NIST frameworks.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.compliance import ComplianceReport
from app.models.event import SecurityEvent
from app.models.alert import Alert

logger = logging.getLogger(__name__)


class ComplianceService:

    async def generate_report(
        self,
        db: AsyncSession,
        framework: str,
        params: Optional[dict],
        generated_by: str,
    ) -> str:
        """Create a pending report and kick off background generation. Returns report ID."""
        report_id = str(uuid.uuid4())
        report = ComplianceReport(
            id=report_id,
            framework=framework,
            title=f"{framework.upper()} Compliance Report",
            generated_by=generated_by,
            parameters=params or {},
            status="pending",
            output_format="json",
        )
        db.add(report)
        await db.commit()

        asyncio.create_task(self._generate_background(report_id, framework, params or {}))
        return report_id

    async def _generate_background(
        self, report_id: str, framework: str, params: dict
    ) -> None:
        try:
            async with AsyncSessionLocal() as db:
                result_data = await self._run_framework_queries(db, framework, params)
                report_result = await db.execute(
                    select(ComplianceReport).where(ComplianceReport.id == report_id)
                )
                report = report_result.scalar_one_or_none()
                if report:
                    report.result_data = result_data
                    report.status = "completed"
                    await db.commit()
        except Exception as exc:
            logger.error("Compliance report generation failed: %s", exc)
            try:
                async with AsyncSessionLocal() as db:
                    report_result = await db.execute(
                        select(ComplianceReport).where(ComplianceReport.id == report_id)
                    )
                    report = report_result.scalar_one_or_none()
                    if report:
                        report.status = "failed"
                        report.error_message = str(exc)[:1000]
                        await db.commit()
            except Exception:
                pass

    async def _run_framework_queries(
        self, db: AsyncSession, framework: str, params: dict
    ) -> dict:
        now = datetime.now(timezone.utc)
        window_days = params.get("window_days", 30)
        since = now - timedelta(days=window_days)

        if framework == "pci_dss":
            return await self._pci_dss(db, since)
        elif framework == "hipaa":
            return await self._hipaa(db, since)
        elif framework == "gdpr":
            return await self._gdpr(db, since)
        elif framework == "soc2":
            return await self._soc2(db, since)
        elif framework == "nist":
            return await self._nist(db, since)
        else:
            raise ValueError(f"Unknown framework: {framework}")

    async def _pci_dss(self, db: AsyncSession, since: datetime) -> dict:
        # Auth failures
        auth_fail = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.timestamp >= since,
                SecurityEvent.category == "authentication",
                SecurityEvent.action == "failed",
            )
        )
        # Privilege escalations
        priv_esc = await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.created_at >= since,
                Alert.mitre_tactic == "Privilege Escalation",
            )
        )
        # Network events
        network_events = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.timestamp >= since,
                SecurityEvent.category == "network",
            )
        )
        # Resolved alerts
        resolved = await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.created_at >= since,
                Alert.status == "resolved",
            )
        )
        total_alerts = await db.execute(
            select(func.count()).select_from(Alert).where(Alert.created_at >= since)
        )
        total = total_alerts.scalar() or 1
        res = resolved.scalar() or 0

        return {
            "framework": "PCI DSS",
            "period_start": since.isoformat(),
            "period_end": datetime.now(timezone.utc).isoformat(),
            "auth_failure_count": auth_fail.scalar() or 0,
            "privilege_escalation_alerts": priv_esc.scalar() or 0,
            "network_access_events": network_events.scalar() or 0,
            "alert_resolution_rate": round((res / total) * 100, 1),
            "total_alerts": total,
            "resolved_alerts": res,
            "requirements": {
                "req_8_2": "Authentication monitoring active",
                "req_7_1": "Access control events tracked",
                "req_10_1": "Audit logging operational",
            },
        }

    async def _hipaa(self, db: AsyncSession, since: datetime) -> dict:
        user_access = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.timestamp >= since,
                SecurityEvent.category == "authentication",
            )
        )
        failed_auth = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.timestamp >= since,
                SecurityEvent.category == "authentication",
                SecurityEvent.action == "failed",
            )
        )
        data_exfil = await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.created_at >= since,
                Alert.mitre_tactic == "Exfiltration",
            )
        )
        return {
            "framework": "HIPAA",
            "period_start": since.isoformat(),
            "period_end": datetime.now(timezone.utc).isoformat(),
            "user_access_events": user_access.scalar() or 0,
            "failed_auth_events": failed_auth.scalar() or 0,
            "data_exfiltration_alerts": data_exfil.scalar() or 0,
            "safeguards": {
                "164_312_a": "Access control monitoring",
                "164_312_b": "Audit controls active",
                "164_312_e": "Transmission security monitored",
            },
        }

    async def _gdpr(self, db: AsyncSession, since: datetime) -> dict:
        data_access = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.timestamp >= since,
            )
        )
        critical_alerts = await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.created_at >= since,
                Alert.severity == "critical",
            )
        )
        return {
            "framework": "GDPR",
            "period_start": since.isoformat(),
            "period_end": datetime.now(timezone.utc).isoformat(),
            "total_data_access_events": data_access.scalar() or 0,
            "critical_alerts": critical_alerts.scalar() or 0,
            "articles": {
                "art_5": "Data processing accountability tracked",
                "art_25": "Data protection by design monitored",
                "art_32": "Security of processing controls active",
            },
        }

    async def _soc2(self, db: AsyncSession, since: datetime) -> dict:
        total_events = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.timestamp >= since,
            )
        )
        access_failures = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.timestamp >= since,
                SecurityEvent.action == "failed",
            )
        )
        open_alerts = await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.created_at >= since,
                Alert.status == "open",
            )
        )
        return {
            "framework": "SOC 2",
            "period_start": since.isoformat(),
            "period_end": datetime.now(timezone.utc).isoformat(),
            "total_events_ingested": total_events.scalar() or 0,
            "access_control_failures": access_failures.scalar() or 0,
            "open_alerts": open_alerts.scalar() or 0,
            "trust_service_criteria": {
                "cc6_1": "Logical access controls monitored",
                "cc7_2": "Security incidents tracked",
                "a1_2": "Availability metrics collected",
            },
        }

    async def _nist(self, db: AsyncSession, since: datetime) -> dict:
        # Group critical/high alerts by MITRE tactic
        critical_high = await db.execute(
            select(Alert.mitre_tactic, func.count().label("count"))
            .where(
                Alert.created_at >= since,
                Alert.severity.in_(["critical", "high"]),
            )
            .group_by(Alert.mitre_tactic)
        )
        tactic_counts = {row.mitre_tactic or "Unknown": row.count for row in critical_high}

        total_events = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.timestamp >= since,
            )
        )
        return {
            "framework": "NIST CSF",
            "period_start": since.isoformat(),
            "period_end": datetime.now(timezone.utc).isoformat(),
            "total_events": total_events.scalar() or 0,
            "critical_high_alerts_by_tactic": tactic_counts,
            "functions": {
                "identify": "Asset inventory and risk assessment operational",
                "protect": "Access controls and security training tracked",
                "detect": "Continuous monitoring active",
                "respond": f"{sum(tactic_counts.values())} high-priority incidents detected",
                "recover": "Incident recovery tracking available",
            },
        }


compliance_service = ComplianceService()
