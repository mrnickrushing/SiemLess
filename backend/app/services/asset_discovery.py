"""Asset discovery service — auto-populates assets from events."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetSoftware, AssetVulnerability
from app.models.event import SecurityEvent

logger = logging.getLogger(__name__)


class AssetDiscoveryService:

    async def upsert_from_event(self, db: AsyncSession, event: SecurityEvent) -> None:
        """Auto-populate or update an asset record from an ingested event."""
        if not event.hostname:
            return

        try:
            result = await db.execute(
                select(Asset).where(Asset.hostname == event.hostname)
            )
            asset = result.scalar_one_or_none()
            now = datetime.now(timezone.utc)

            if asset:
                asset.last_seen = now
                if event.source_ip:
                    ips = list(asset.ip_addresses or [])
                    if event.source_ip not in ips:
                        ips.append(event.source_ip)
                        asset.ip_addresses = ips
            else:
                asset = Asset(
                    id=str(uuid.uuid4()),
                    hostname=event.hostname,
                    ip_addresses=[event.source_ip] if event.source_ip else [],
                    first_seen=now,
                    last_seen=now,
                )
                db.add(asset)

            await db.flush()
        except Exception as exc:
            logger.debug("Asset discovery upsert failed: %s", exc)

    async def enrich_cves(self, db: AsyncSession, asset_id: str) -> int:
        """Query NVD API for CVEs for each software entry on this asset."""
        software_result = await db.execute(
            select(AssetSoftware).where(AssetSoftware.asset_id == asset_id)
        )
        software_list = software_result.scalars().all()

        count = 0
        for sw in software_list:
            if not sw.cpe:
                continue
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        "https://services.nvd.nist.gov/rest/json/cves/2.0",
                        params={"cpeName": sw.cpe},
                    )
                    if resp.status_code != 200:
                        continue
                    cves = resp.json().get("vulnerabilities", [])
                    for cve_data in cves[:20]:
                        cve = cve_data.get("cve", {})
                        cve_id = cve.get("id", "")
                        if not cve_id:
                            continue

                        # Check if already exists
                        existing = await db.execute(
                            select(AssetVulnerability).where(
                                AssetVulnerability.asset_id == asset_id,
                                AssetVulnerability.cve_id == cve_id,
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue

                        metrics = cve.get("metrics", {})
                        cvss_data = (
                            metrics.get("cvssMetricV31", [{}])[0]
                            if metrics.get("cvssMetricV31")
                            else metrics.get("cvssMetricV30", [{}])[0]
                            if metrics.get("cvssMetricV30")
                            else {}
                        )
                        cvss_score = cvss_data.get("cvssData", {}).get("baseScore")
                        severity = _cvss_to_severity(cvss_score)

                        descriptions = cve.get("descriptions", [])
                        description = next(
                            (d["value"] for d in descriptions if d.get("lang") == "en"),
                            None,
                        )

                        vuln = AssetVulnerability(
                            id=str(uuid.uuid4()),
                            asset_id=asset_id,
                            cve_id=cve_id,
                            cvss_score=cvss_score,
                            description=description,
                            severity=severity,
                        )
                        db.add(vuln)
                        count += 1
            except Exception as exc:
                logger.warning("CVE enrichment failed for %s: %s", sw.cpe, exc)

        # Update CVE count on asset
        if count > 0:
            asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
            asset = asset_result.scalar_one_or_none()
            if asset:
                vuln_count_result = await db.execute(
                    select(AssetVulnerability).where(AssetVulnerability.asset_id == asset_id)
                )
                asset.cve_count = len(vuln_count_result.scalars().all())

        await db.commit()
        return count


def _cvss_to_severity(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


asset_discovery_service = AssetDiscoveryService()
