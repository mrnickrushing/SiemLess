"""MISP threat intelligence feed connector."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.feed_connectors.base import BaseFeedConnector

logger = logging.getLogger(__name__)

_MISP_TO_INDICATOR_TYPE = {
    "ip-src": "ip",
    "ip-dst": "ip",
    "domain": "domain",
    "hostname": "domain",
    "md5": "hash_md5",
    "sha1": "hash_sha1",
    "sha256": "hash_sha256",
    "url": "url",
    "email-src": "email",
    "email-dst": "email",
}


class MISPFeedConnector(BaseFeedConnector):

    async def pull(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        """
        Fetches recent attributes from the configured MISP instance and upserts them as ThreatIndicator records.
        
        Attributes whose MISP type is unmapped or whose value is empty are skipped. The database session is committed only if at least one new indicator is added.
        
        Parameters:
            since (Optional[datetime]): Fetch attributes modified at or after this timestamp. If omitted, defaults to now minus 1 day (UTC).
        
        Returns:
            int: Number of indicators newly inserted into the database.
        
        Raises:
            Exception: If the HTTP request to the MISP REST search endpoint fails or the response cannot be processed.
        """
        from app.models.threat_intel import ThreatIndicator

        start = since or (datetime.now(timezone.utc) - timedelta(days=1))

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.url.rstrip('/')}/attributes/restSearch",
                    headers={
                        "Authorization": self.api_key or "",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={
                        "returnFormat": "json",
                        "limit": 1000,
                        "timestamp": int(start.timestamp()),
                    },
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("MISP restSearch failed: %s", exc)
            raise

        attrs = resp.json().get("response", {}).get("Attribute", [])
        count = 0

        for attr in attrs:
            attr_type = attr.get("type", "")
            indicator_type = _MISP_TO_INDICATOR_TYPE.get(attr_type)
            if not indicator_type:
                continue

            value = attr.get("value", "").strip()
            if not value:
                continue

            # Upsert indicator
            try:
                existing = await db.execute(
                    select(ThreatIndicator).where(
                        ThreatIndicator.indicator_type == indicator_type,
                        ThreatIndicator.value == value,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                now = datetime.now(timezone.utc)
                indicator = ThreatIndicator(
                    id=uuid.uuid4(),
                    indicator_type=indicator_type,
                    value=value,
                    confidence=70,
                    severity="medium",
                    source="misp",
                    tags=["misp", attr.get("category", "")],
                    first_seen=now,
                    last_seen=now,
                    description=attr.get("comment", ""),
                )
                db.add(indicator)
                count += 1
            except Exception as exc:
                logger.debug("MISP indicator upsert failed: %s", exc)

        if count > 0:
            await db.commit()

        return count
