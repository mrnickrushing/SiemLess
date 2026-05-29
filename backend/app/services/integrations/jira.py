"""Jira integration using REST API v3."""
import logging
from typing import Optional

import httpx

from app.services.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class JiraIntegration(BaseIntegration):

    def __init__(self, config: dict):
        """
        Initialize a JiraIntegration instance using configuration values.
        
        Parameters:
            config (dict): Configuration mapping with required keys:
                - "url" (str): Base Jira URL; any trailing '/' will be removed.
                - "username" (str): Username for HTTP basic auth.
                - "api_token" (str): API token for HTTP basic auth.
                - "project_key" (str): Default Jira project key to use when creating issues.
        
        Attributes:
            base_url (str): Normalized Jira base URL without a trailing slash.
            auth (tuple): HTTP basic auth tuple (username, api_token).
            project_key (str): Default project key for issue operations.
        """
        self.base_url = config["url"].rstrip("/")
        self.auth = (config["username"], config["api_token"])
        self.project_key = config["project_key"]

    async def create_ticket(self, title: str, description: str, priority: str) -> str:
        """
        Create a Jira issue of type "Bug" in the configured project and return its issue key.
        
        Parameters:
            title (str): Issue summary; will be truncated to 255 characters.
            description (str): Issue description; will be embedded as a Jira "doc" body and truncated to 5000 characters.
            priority (str): Priority name to assign to the issue (e.g., "High", "Medium", "Low").
        
        Returns:
            issue_key (str): The created issue key (for example, "SIEMLESS-42").
        """
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
        """
        Post a comment to a Jira issue when a comment is provided.
        
        Parameters:
            ticket_id (str): The Jira issue key or ID to which the comment will be posted.
            status (str): Intended new status for the issue; currently not applied by this method.
            comment (Optional[str]): Comment text to add to the issue. If falsy, no request is made.
        
        Notes:
            Sends a POST request to the Jira REST API comment endpoint using the integration's configured base URL and authentication.
        """
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
        """
        Checks whether the configured Jira instance can be reached and authenticated.
        
        Returns:
            `True` if the request returns HTTP 200, `False` otherwise or if an exception occurs.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/rest/api/3/myself",
                    auth=self.auth,
                )
                return resp.status_code == 200
        except Exception:
            return False
