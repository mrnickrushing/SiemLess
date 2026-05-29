"""OpenCTI threat intelligence feed connector via GraphQL."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.feed_connectors.base import BaseFeedConnector

logger = logging.getLogger(__name__)

_OPENCTI_TO_INDICATOR_TYPE = {
    "IPv4-Addr": "ip",
    "IPv6-Addr": "ip",
    "Domain-Name": "domain",
    "Url": "url",
    "StixFile": "hash_sha256",
    "Email-Addr": "email",
}

_GQL_QUERY = """
query GetIndicators($first: Int, $after: String) {
  indicators(first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        name
        pattern_type
        indicator_types
        valid_from
        confidence
        observables {
          edges {
            node {
              entity_type
              ... on IPv4Addr { value }
              ... on DomainName { value }
              ... on Url { value }
            }
          }
        }
      }
    }
  }
}
"""


class OpenCTIFeedConnector(BaseFeedConnector):

    async def pull(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        from app.models.threat_intel import ThreatIndicator

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.url.rstrip('/')}/graphql",
                    headers={
                        "Authorization": f"Bearer {self.api_key or ''}",
                        "Content-Type": "application/json",
                    },
                    json={"query": _GQL_QUERY, "variables": {"first": 500}},
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("OpenCTI GraphQL query failed: %s", exc)
            raise

        data = resp.json().get("data", {})
        edges = data.get("indicators", {}).get("edges", [])
        count = 0
        now = datetime.now(timezone.utc)

        for edge in edges:
            node = edge.get("node", {})
            observables = node.get("observables", {}).get("edges", [])
            for obs_edge in observables:
                obs = obs_edge.get("node", {})
                entity_type = obs.get("entity_type", "")
                indicator_type = _OPENCTI_TO_INDICATOR_TYPE.get(entity_type)
                value = obs.get("value", "")

                if not indicator_type or not value:
                    continue

                try:
                    existing = await db.execute(
                        select(ThreatIndicator).where(
                            ThreatIndicator.indicator_type == indicator_type,
                            ThreatIndicator.value == value,
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        continue

                    confidence = node.get("confidence") or 50
                    indicator = ThreatIndicator(
                        id=uuid.uuid4(),
                        indicator_type=indicator_type,
                        value=value,
                        confidence=int(confidence),
                        severity="medium",
                        source="opencti",
                        tags=["opencti"] + (node.get("indicator_types") or []),
                        first_seen=now,
                        last_seen=now,
                        description=node.get("name", ""),
                    )
                    db.add(indicator)
                    count += 1
                except Exception as exc:
                    logger.debug("OpenCTI indicator upsert failed: %s", exc)

        if count > 0:
            await db.commit()

        return count
