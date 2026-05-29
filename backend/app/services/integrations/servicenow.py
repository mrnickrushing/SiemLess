"""ServiceNow integration using Table API."""
import logging
from typing import Optional

import httpx

from app.services.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

_PRIORITY_MAP = {
    "Critical": "1",
    "High": "2",
    "Medium": "3",
    "Low": "4",
    "Info": "5",
}


class ServiceNowIntegration(BaseIntegration):

    def __init__(self, config: dict):
        self.base_url = config["url"].rstrip("/")
        self.auth = (config["username"], config["password"])
        self.table = config.get("table", "incident")

    async def create_ticket(self, title: str, description: str, priority: str) -> str:
        sn_priority = _PRIORITY_MAP.get(priority.capitalize(), "3")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/now/table/{self.table}",
                auth=self.auth,
                json={
                    "short_description": title[:255],
                    "description": description[:5000],
                    "priority": sn_priority,
                    "category": "security",
                },
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", {}).get("number") or data.get("result", {}).get("sys_id", "unknown")

    async def update_ticket(self, ticket_id: str, status: str, comment: Optional[str] = None) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.patch(
                f"{self.base_url}/api/now/table/{self.table}/{ticket_id}",
                auth=self.auth,
                json={"work_notes": comment or f"Status updated to: {status}"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/api/now/table/{self.table}?sysparm_limit=1",
                    auth=self.auth,
                    headers={"Accept": "application/json"},
                )
                return resp.status_code == 200
        except Exception:
            return False
