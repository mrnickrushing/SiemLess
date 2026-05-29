"""RBAC service — role hierarchy checks."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rbac import OrgUser

logger = logging.getLogger(__name__)

_ROLE_LEVELS = {"admin": 3, "analyst": 2, "readonly": 1}


class RBACService:

    async def has_role(
        self, db: AsyncSession, username: str, required_role: str
    ) -> bool:
        """Check if a user has at least the required role level."""
        try:
            result = await db.execute(
                select(OrgUser).where(OrgUser.username == username)
            )
            user = result.scalar_one_or_none()
            if user is None:
                # Not in org_users — backward-compatible single-user mode, grant access
                return True
            required_level = _ROLE_LEVELS.get(required_role, 1)
            user_level = _ROLE_LEVELS.get(user.role, 0)
            return user_level >= required_level
        except Exception as exc:
            logger.debug("RBAC check failed: %s", exc)
            return True  # Fail-open for backward compat


rbac_service = RBACService()
