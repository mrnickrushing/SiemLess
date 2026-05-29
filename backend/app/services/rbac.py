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
        """
        Determine whether a user meets or exceeds a required role level.
        
        Checks the stored role for `username` and compares its hierarchy level to `required_role`. If the user is not present in the organization records or an error occurs during the check, the function returns `True` (fail-open) for backward compatibility. Unknown `required_role` values default to level 1; unknown stored user roles are treated as level 0.
        
        Parameters:
            username (str): The username to look up.
            required_role (str): The role required for access (e.g., "admin", "analyst", "readonly").
        
        Returns:
            bool: `True` if the user's role level is greater than or equal to the required role level; `False` otherwise. `True` is also returned when the user is not found or an exception occurs.
        """
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
