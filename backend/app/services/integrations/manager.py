"""Integration manager — factory for ticketing integrations."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import IntegrationConfig
from app.services.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class IntegrationManager:

    def _get_integration(self, row: IntegrationConfig) -> BaseIntegration:
        """
        Create a concrete BaseIntegration instance configured from a persisted IntegrationConfig row.
        
        Parameters:
            row (IntegrationConfig): Database row containing `integration_type` and optional `config` dict used to instantiate the integration.
        
        Returns:
            BaseIntegration: An instance of the integration implementation configured with `row.config` (or an empty dict if unset).
        
        Raises:
            ValueError: If `row.integration_type` is not a supported integration type.
        """
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
        """
        Resolve an enabled integration configuration by ID and return the corresponding integration instance.
        
        Parameters:
            db (AsyncSession): Database session used to load the integration configuration.
            integration_id (str): Identifier of the integration configuration to resolve.
        
        Returns:
            BaseIntegration: An instance of the integration configured for the requested ID.
        
        Raises:
            ValueError: If no enabled integration with the given ID exists.
        """
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
        """
        Create a ticket in the specified integration and return the integration's ticket identifier.
        
        Resolves the enabled integration by `integration_id` and delegates ticket creation to that integration.
        
        Parameters:
            integration_id (str): Identifier of the integration configuration to use.
            title (str): Ticket title.
            description (str): Ticket description/details.
            priority (str): Ticket priority; defaults to "Medium".
        
        Returns:
            str: External ticket identifier returned by the integration.
        """
        integration = await self.get_integration(db, integration_id)
        return await integration.create_ticket(title, description, priority)

    async def test_connection(self, db: AsyncSession, integration_id: str) -> bool:
        """
        Verify connectivity for the specified integration.
        
        Resolves the integration configuration identified by `integration_id` and performs the integration-specific connection check.
        
        Parameters:
            integration_id (str): Identifier of the integration to test.
        
        Returns:
            `True` if the integration responds and credentials are valid, `False` otherwise.
        """
        integration = await self.get_integration(db, integration_id)
        return await integration.test_connection()


integration_manager = IntegrationManager()
