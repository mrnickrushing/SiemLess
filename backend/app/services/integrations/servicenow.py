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
        """
        Initialize the integration with ServiceNow connection settings.
        
        Parameters:
            config (dict): Configuration dictionary with the following keys:
                - url (str): Base ServiceNow URL; trailing slash will be removed.
                - username (str): Username for basic authentication.
                - password (str): Password for basic authentication.
                - table (str, optional): Table name to operate on; defaults to `"incident"`.
        """
        self.base_url = config["url"].rstrip("/")
        self.auth = (config["username"], config["password"])
        self.table = config.get("table", "incident")

    async def create_ticket(self, title: str, description: str, priority: str) -> str:
        """
        Create a ServiceNow ticket in the configured table.
        
        Parameters:
            title (str): Short description for the ticket (truncated to 255 characters).
            description (str): Detailed description for the ticket (truncated to 5000 characters).
            priority (str): Human-readable priority (e.g., "Critical", "High", "Medium", "Low", "Info"); mapped to ServiceNow numeric priority (defaults to "3" when unrecognized).
        
        Returns:
            ticket_id (str): The ticket identifier returned by ServiceNow: `result.number` if present, otherwise `result.sys_id`, or `"unknown"` if neither is available.
        
        Raises:
            httpx.HTTPStatusError: If the HTTP request returns a non-2xx status.
        """
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
        """
        Update a ServiceNow record's work notes for the given ticket.
        
        Parameters:
            ticket_id (str): ServiceNow record identifier (sys_id or table-specific id) to patch.
            status (str): New status value used when composing the default work note.
            comment (Optional[str]): Optional work note text; if omitted, a note of the form
                "Status updated to: {status}" will be written.
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.patch(
                f"{self.base_url}/api/now/table/{self.table}/{ticket_id}",
                auth=self.auth,
                json={"work_notes": comment or f"Status updated to: {status}"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )

    async def test_connection(self) -> bool:
        """
        Check whether the configured ServiceNow table API endpoint is reachable and responding.
        
        Performs a lightweight GET to the configured table endpoint and returns `true` only when the HTTP response status code is 200; any exception or non-200 response yields `false`.
        
        Returns:
            bool: `true` if the endpoint responds with HTTP 200, `false` otherwise.
        """
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
