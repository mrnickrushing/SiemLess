"""Jira integration using REST API v3."""
import logging
from typing import Optional

import httpx

from app.services.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class JiraIntegration(BaseIntegration):

    def __init__(self, config: dict):
        self.base_url = config["url"].rstrip("/")
        self.auth = (config["username"], config["api_token"])
        self.project_key = config["project_key"]

    async def create_ticket(self, title: str, description: str, priority: str) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/rest/api/3/issue",
                auth=self.auth,
                json={
                    "fields": {
                        "project": {"key": self.project_key},
                        "summary": title[:255],
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": description[:5000]}],
                                }
                            ],
                        },
                        "issuetype": {"name": "Bug"},
                        "priority": {"name": priority},
                    }
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["key"]  # e.g. "SIEMLESS-42"

    async def update_ticket(self, ticket_id: str, status: str, comment: Optional[str] = None) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if comment:
                await client.post(
                    f"{self.base_url}/rest/api/3/issue/{ticket_id}/comment",
                    auth=self.auth,
                    json={
                        "body": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": comment}],
                                }
                            ],
                        }
                    },
                )

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/rest/api/3/myself",
                    auth=self.auth,
                )
                return resp.status_code == 200
        except Exception:
            return False
