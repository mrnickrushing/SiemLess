"""Integration manager — factory for ticketing integrations."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import IntegrationConfig
from app.services.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class IntegrationManager:

    def _get_integration(self, row: IntegrationConfig) -> BaseIntegration:
        config = row.config or {}
        if row.integration_type == "jira":
            from app.services.integrations.jira import JiraIntegration
            return JiraIntegration(config)
        elif row.integration_type == "servicenow":
            from app.services.integrations.servicenow import ServiceNowIntegration
            return ServiceNowIntegration(config)
        else:
            raise ValueError(f"Unknown integration type: {row.integration_type}")

    async def get_integration(self, db: AsyncSession, integration_id: str) -> BaseIntegration:
        result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.id == integration_id,
                IntegrationConfig.enabled == True,  # noqa: E712
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Integration {integration_id} not found or disabled")
        return self._get_integration(row)

    async def create_ticket(
        self,
        db: AsyncSession,
        integration_id: str,
        title: str,
        description: str,
        priority: str = "Medium",
    ) -> str:
        integration = await self.get_integration(db, integration_id)
        return await integration.create_ticket(title, description, priority)

    async def test_connection(self, db: AsyncSession, integration_id: str) -> bool:
        integration = await self.get_integration(db, integration_id)
        return await integration.test_connection()


integration_manager = IntegrationManager()
