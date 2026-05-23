from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User

# In-process cache: permission_key → set of allowed roles
_perm_cache: dict[str, set[str]] = {}


def invalidate_perm_cache() -> None:
    _perm_cache.clear()


def require_roles(*roles: str):
    """Dependency: current user must have one of the given roles (hardcoded)."""
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return checker


def require_permission(perm_key: str):
    """Dependency: current user's role must have the given permission (DB-backed)."""
    async def checker(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        if perm_key not in _perm_cache:
            from app.models.role_permission import RolePermission
            result = await db.execute(
                select(RolePermission.role).where(RolePermission.permission_key == perm_key)
            )
            _perm_cache[perm_key] = {r for (r,) in result.all()}
        if current_user.role not in _perm_cache[perm_key]:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return checker


def require_admin():
    return require_roles("admin")


def require_pm_or_admin():
    return require_roles("pm", "admin")


def require_pm_sales_admin():
    return require_roles("pm", "sales", "admin")
