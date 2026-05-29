"""Base class for cloud log connectors."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


class BaseConnector(ABC):
    def __init__(self, config: dict):
        """
        Initialize the connector with its configuration.
        
        Parameters:
            config (dict): Configuration mapping for the connector; stored on the instance as `self.config`.
        """
        self.config = config

    @abstractmethod
    async def poll(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        """
        Poll for new events from the connector and ingest them into storage.
        
        Parameters:
            db (AsyncSession): Async SQLAlchemy session used to persist ingested events.
            since (Optional[datetime]): Retrieve events occurring at or after this timestamp; if omitted, use the connector's default starting point.
        
        Returns:
            int: Number of events successfully ingested.
        """
