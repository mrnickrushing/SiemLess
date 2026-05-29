"""Base class for threat feed connectors."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


class BaseFeedConnector(ABC):
    def __init__(self, url: str, api_key: Optional[str] = None, config: Optional[dict] = None):
        """
        Initialize the connector with its source URL, optional API key, and optional configuration.
        
        Parameters:
            url (str): Feed endpoint or source URL.
            api_key (Optional[str]): API key or token used to authenticate with the feed, if required.
            config (Optional[dict]): Optional connector-specific configuration; defaults to an empty dict when not provided.
        """
        self.url = url
        self.api_key = api_key
        self.config = config or {}

    @abstractmethod
    async def pull(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        """
        Fetches new threat indicators from the feed and inserts them into the database.
        
        Parameters:
            db (AsyncSession): Database session used to persist fetched indicators.
            since (Optional[datetime]): If provided, only indicators with a timestamp later than this value are considered.
        
        Returns:
            int: The number of indicators added to the database.
        """
