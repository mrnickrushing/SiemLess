"""Base class for ticketing integrations."""
from abc import ABC, abstractmethod
from typing import Optional


class BaseIntegration(ABC):

    @abstractmethod
    async def create_ticket(self, title: str, description: str, priority: str) -> str:
        """Create a ticket. Returns ticket ID/URL."""

    @abstractmethod
    async def update_ticket(self, ticket_id: str, status: str, comment: Optional[str] = None) -> None:
        """Update an existing ticket."""

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify credentials work. Returns True if connection succeeds."""
