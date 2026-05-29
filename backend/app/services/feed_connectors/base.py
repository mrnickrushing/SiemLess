"""Base class for threat feed connectors."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


class BaseFeedConnector(ABC):
    def __init__(self, url: str, api_key: Optional[str] = None, config: Optional[dict] = None):
        self.url = url
        self.api_key = api_key
        self.config = config or {}

    @abstractmethod
    async def pull(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        """Pull new indicators into the threat intel DB. Returns count added."""
