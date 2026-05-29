"""Base class for cloud log connectors."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


class BaseConnector(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def poll(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        """Pull new events, store via store_event(), return count ingested."""
