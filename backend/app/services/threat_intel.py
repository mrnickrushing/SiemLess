"""
Threat intelligence service: checks IPs, hashes, and domains against
local DB and optionally external APIs (AbuseIPDB, VirusTotal).
"""
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.threat_intel import ThreatIndicator

logger = logging.getLogger(__name__)

# Regex helpers
RE_IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
RE_MD5 = re.compile(r"^[a-fA-F0-9]{32}$")
RE_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
RE_SHA1 = re.compile(r"^[a-fA-F0-9]{40}$")
RE_DOMAIN = re.compile(r"^(?:[a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,}$")
RE_URL = re.compile(r"^https?://")
RE_EMAIL = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


def _detect_indicator_type(value: str) -> str:
    value = value.strip()
    if RE_IPV4.match(value):
        return "ip"
    if RE_MD5.match(value):
        return "hash_md5"
    if RE_SHA256.match(value):
        return "hash_sha256"
    if RE_SHA1.match(value):
        return "hash_sha1"
    if RE_URL.match(value):
        return "url"
    if RE_EMAIL.match(value):
        return "email"
    if RE_DOMAIN.match(value):
        return "domain"
    return "unknown"


class ThreatIntelService:
    """Checks indicators against internal DB and optional external feeds."""

    def __init__(self) -> None:
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # -----------------------------------------------------------------------
    # Public check methods
    # -----------------------------------------------------------------------

    async def check_ip(self, db: AsyncSession, ip: str) -> dict:
        """Check an IP against internal DB then optionally AbuseIPDB."""
        result = await self._check_db(db, "ip", ip)
        if result["found"]:
            return result

        if settings.THREAT_INTEL_ABUSEIPDB_KEY:
            try:
                external = await self._query_abuseipdb(ip)
                if external:
                    result.update(external)
                    result["found"] = True
                    # Persist to DB for caching
                    await self._persist_indicator(db, "ip", ip, external)
            except Exception as exc:
                logger.warning("AbuseIPDB query failed for %s: %s", ip, exc)

        return result

    async def check_hash(self, db: AsyncSession, hash_value: str) -> dict:
        """Check a file hash against internal DB then optionally VirusTotal."""
        indicator_type = _detect_indicator_type(hash_value)
        if indicator_type not in ("hash_md5", "hash_sha256", "hash_sha1"):
            indicator_type = "hash_md5"

        result = await self._check_db(db, indicator_type, hash_value)
        if result["found"]:
            return result

        if settings.THREAT_INTEL_VIRUSTOTAL_KEY:
            try:
                external = await self._query_virustotal_hash(hash_value)
                if external:
                    result.update(external)
                    result["found"] = True
                    await self._persist_indicator(db, indicator_type, hash_value, external)
            except Exception as exc:
                logger.warning("VirusTotal hash query failed for %s: %s", hash_value, exc)

        return result

    async def check_domain(self, db: AsyncSession, domain: str) -> dict:
        """Check a domain against internal DB then optionally VirusTotal."""
        result = await self._check_db(db, "domain", domain)
        if result["found"]:
            return result

        if settings.THREAT_INTEL_VIRUSTOTAL_KEY:
            try:
                external = await self._query_virustotal_domain(domain)
                if external:
                    result.update(external)
                    result["found"] = True
                    await self._persist_indicator(db, "domain", domain, external)
            except Exception as exc:
                logger.warning("VirusTotal domain query failed for %s: %s", domain, exc)

        return result

    async def check_indicator(self, db: AsyncSession, value: str, indicator_type: Optional[str] = None) -> dict:
        """Auto-detect type and check."""
        if not indicator_type:
            indicator_type = _detect_indicator_type(value)

        if indicator_type == "ip":
            return await self.check_ip(db, value)
        if indicator_type in ("hash_md5", "hash_sha256", "hash_sha1"):
            return await self.check_hash(db, value)
        if indicator_type == "domain":
            return await self.check_domain(db, value)

        return await self._check_db(db, indicator_type, value)

    async def enrich_event(self, db: AsyncSession, event_dict: dict) -> dict:
        """Enrich an event dict by checking IPs and hashes against threat intel."""
        threat_matches = []

        source_ip = event_dict.get("source_ip")
        if source_ip and RE_IPV4.match(str(source_ip)):
            ip_result = await self.check_ip(db, source_ip)
            if ip_result.get("found"):
                threat_matches.append({"type": "ip", "value": source_ip, "detail": ip_result})

        dest_ip = event_dict.get("destination_ip")
        if dest_ip and RE_IPV4.match(str(dest_ip)):
            ip_result = await self.check_ip(db, dest_ip)
            if ip_result.get("found"):
                threat_matches.append({"type": "ip", "value": dest_ip, "detail": ip_result})

        pf = event_dict.get("parsed_fields") or {}
        for field in ("hash", "md5", "sha256", "file_hash"):
            hash_val = pf.get(field)
            if hash_val and isinstance(hash_val, str):
                hash_result = await self.check_hash(db, hash_val)
                if hash_result.get("found"):
                    threat_matches.append({"type": "hash", "value": hash_val, "detail": hash_result})

        if threat_matches:
            if event_dict.get("parsed_fields") is None:
                event_dict["parsed_fields"] = {}
            event_dict["parsed_fields"]["threat_matches"] = threat_matches
            # Add tag for correlation engine
            tags = event_dict.get("tags") or []
            if "threat-match" not in tags:
                tags.append("threat-match")
            event_dict["tags"] = tags

        return event_dict

    async def bulk_import_indicators(self, db: AsyncSession, indicators: list[dict]) -> int:
        """Import a list of indicator dicts; return count of newly inserted."""
        imported = 0
        for ind in indicators:
            value = ind.get("value", "").strip()
            if not value:
                continue
            indicator_type = ind.get("indicator_type") or _detect_indicator_type(value)
            if indicator_type == "unknown":
                continue

            # Check if already exists
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
                confidence=ind.get("confidence", 75),
                severity=ind.get("severity", "medium"),
                source=ind.get("source", "manual"),
                tags=ind.get("tags", []),
                first_seen=now,
                last_seen=now,
                description=ind.get("description", ""),
                raw_data=ind.get("raw_data"),
            )
            db.add(indicator)
            imported += 1

        await db.flush()
        return imported

    # -----------------------------------------------------------------------
    # Internal DB helpers
    # -----------------------------------------------------------------------

    async def _check_db(self, db: AsyncSession, indicator_type: str, value: str) -> dict:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ThreatIndicator).where(
                ThreatIndicator.indicator_type == indicator_type,
                ThreatIndicator.value == value,
            )
        )
        indicator = result.scalar_one_or_none()

        if indicator is None:
            return {"found": False, "indicator_type": indicator_type, "value": value}

        # Check expiry
        if indicator.expiry and indicator.expiry < now:
            return {"found": False, "indicator_type": indicator_type, "value": value, "expired": True}

        # Update last_seen
        indicator.last_seen = now
        db.add(indicator)

        return {
            "found": True,
            "indicator_type": indicator_type,
            "value": value,
            "confidence": indicator.confidence,
            "severity": indicator.severity,
            "source": indicator.source,
            "tags": indicator.tags,
            "description": indicator.description,
            "first_seen": indicator.first_seen.isoformat() if indicator.first_seen else None,
            "last_seen": now.isoformat(),
        }

    async def _persist_indicator(
        self, db: AsyncSession, indicator_type: str, value: str, data: dict
    ) -> None:
        now = datetime.now(timezone.utc)
        existing = await db.execute(
            select(ThreatIndicator).where(
                ThreatIndicator.indicator_type == indicator_type,
                ThreatIndicator.value == value,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return

        indicator = ThreatIndicator(
            id=uuid.uuid4(),
            indicator_type=indicator_type,
            value=value,
            confidence=data.get("confidence", 50),
            severity=data.get("severity", "medium"),
            source=data.get("source", "external"),
            tags=data.get("tags", []),
            first_seen=now,
            last_seen=now,
            description=data.get("description", ""),
            raw_data=data.get("raw_data"),
        )
        db.add(indicator)
        try:
            await db.flush()
        except Exception as exc:
            logger.warning("Could not persist threat indicator %s/%s: %s", indicator_type, value, exc)
            await db.rollback()

    # -----------------------------------------------------------------------
    # External API queries
    # -----------------------------------------------------------------------

    async def _query_abuseipdb(self, ip: str) -> Optional[dict]:
        """Query AbuseIPDB v2 API."""
        url = "https://api.abuseipdb.com/api/v2/check"
        headers = {
            "Key": settings.THREAT_INTEL_ABUSEIPDB_KEY,
            "Accept": "application/json",
        }
        params = {"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""}

        resp = await self.http.get(url, headers=headers, params=params)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", {})

        abuse_score = data.get("abuseConfidenceScore", 0)
        if abuse_score < 10:
            return None

        severity = "low"
        if abuse_score >= 80:
            severity = "critical"
        elif abuse_score >= 50:
            severity = "high"
        elif abuse_score >= 20:
            severity = "medium"

        return {
            "found": True,
            "confidence": abuse_score,
            "severity": severity,
            "source": "abuseipdb",
            "description": f"AbuseIPDB confidence score: {abuse_score}%",
            "tags": ["abuseipdb", "malicious-ip"],
            "raw_data": data,
        }

    async def _query_virustotal_hash(self, file_hash: str) -> Optional[dict]:
        """Query VirusTotal v3 API for a file hash."""
        url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
        headers = {"x-apikey": settings.THREAT_INTEL_VIRUSTOTAL_KEY}

        resp = await self.http.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        body = resp.json()
        attributes = body.get("data", {}).get("attributes", {})
        last_analysis = attributes.get("last_analysis_stats", {})
        malicious = last_analysis.get("malicious", 0)
        total = sum(last_analysis.values()) or 1

        if malicious == 0:
            return None

        confidence = int((malicious / total) * 100)
        severity = "critical" if confidence >= 70 else "high" if confidence >= 40 else "medium"

        return {
            "found": True,
            "confidence": confidence,
            "severity": severity,
            "source": "virustotal",
            "description": f"VirusTotal: {malicious}/{total} engines flagged as malicious",
            "tags": ["virustotal", "malware"],
            "raw_data": {
                "malicious": malicious,
                "total": total,
                "sha256": attributes.get("sha256"),
                "meaningful_name": attributes.get("meaningful_name"),
            },
        }

    async def _query_virustotal_domain(self, domain: str) -> Optional[dict]:
        """Query VirusTotal v3 API for a domain."""
        url = f"https://www.virustotal.com/api/v3/domains/{domain}"
        headers = {"x-apikey": settings.THREAT_INTEL_VIRUSTOTAL_KEY}

        resp = await self.http.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        body = resp.json()
        attributes = body.get("data", {}).get("attributes", {})
        last_analysis = attributes.get("last_analysis_stats", {})
        malicious = last_analysis.get("malicious", 0)
        total = sum(last_analysis.values()) or 1

        if malicious == 0:
            return None

        confidence = int((malicious / total) * 100)
        severity = "critical" if confidence >= 70 else "high" if confidence >= 40 else "medium"

        return {
            "found": True,
            "confidence": confidence,
            "severity": severity,
            "source": "virustotal",
            "description": f"VirusTotal domain: {malicious}/{total} engines flagged",
            "tags": ["virustotal", "malicious-domain"],
            "raw_data": last_analysis,
        }


# Module-level singleton
threat_intel_service = ThreatIntelService()
