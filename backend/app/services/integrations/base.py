"""Base class for ticketing integrations."""
from abc import ABC, abstractmethod
from typing import Optional


class BaseIntegration(ABC):

    @abstractmethod
    async def create_ticket(self, title: str, description: str, priority: str) -> str:
        """
        Create a new ticket in the integration system with the provided title, description, and priority.
        
        Parameters:
            title (str): Short, descriptive title for the ticket.
            description (str): Detailed description of the issue or request.
            priority (str): Priority level as recognized by the integration (e.g., "low", "medium", "high").
        
        Returns:
            str: Identifier or URL of the created ticket.
        """

    @abstractmethod
    async def update_ticket(self, ticket_id: str, status: str, comment: Optional[str] = None) -> None:
        """
        Update the ticket identified by ticket_id by setting its status and optionally adding a comment.
        
        Parameters:
            ticket_id (str): Identifier or URL of the ticket to update.
            status (str): New status to apply to the ticket.
            comment (Optional[str]): Optional comment to attach to the ticket.
        """

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Verify that the integration credentials and connectivity are valid.
        
        Returns:
            bool: `True` if the connection succeeds, `False` otherwise.
        """
