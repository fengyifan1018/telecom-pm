from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.role_permission import RolePermission
from app.permissions import require_permission, invalidate_perm_cache
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/permissions", tags=["permissions"])

ALL_ROLES = ["admin", "pm", "sales", "operations", "procurement", "network_engineer", "field_engineer"]

ROLE_LABELS = {
    "admin": "管理员",
    "pm": "项目经理",
    "sales": "销售",
    "operations": "运营",
    "procurement": "采购",
    "network_engineer": "网络工程师",
    "field_engineer": "现场实施",
}

# Ordered permission definitions
PERMISSION_DEFS: dict[str, dict] = {
    "project.create":    {"label": "创建项目",          "default_roles": ["sales", "pm", "admin"]},
    "project.initiate":  {"label": "立项（生成任务）",   "default_roles": ["pm", "admin"]},
    "project.suspend":   {"label": "暂停项目",          "default_roles": ["pm", "admin"]},
    "project.resume":    {"label": "恢复项目",          "default_roles": ["pm", "admin"]},
    "project.delete":    {"label": "删除项目",          "default_roles": ["admin"]},
    "task.assign":       {"label": "指派任务",          "default_roles": ["pm", "admin"]},
    "task.approve":      {"label": "审核任务",          "default_roles": ["pm", "admin"]},
    "cr.create":         {"label": "提交变更申请",       "default_roles": ["sales", "pm", "admin"]},
    "cr.approve":        {"label": "审批变更申请",       "default_roles": ["pm", "admin"]},
    "report.view":       {"label": "查看报表",          "default_roles": ["pm", "admin", "operations"]},
    "template.manage":   {"label": "模板管理",          "default_roles": ["admin"]},
    "user.manage":       {"label": "用户管理",          "default_roles": ["admin"]},
    "group.manage":      {"label": "用户组管理",        "default_roles": ["admin"]},
    "permission.manage": {"label": "权限管理",          "default_roles": ["admin"]},
    # Menu visibility
    "menu.reports":      {"label": "菜单：报表中心",    "default_roles": ["admin", "pm", "sales", "operations", "procurement", "network_engineer", "field_engineer"]},
    "menu.templates":    {"label": "菜单：模板管理",    "default_roles": ["admin", "pm", "operations", "procurement", "network_engineer", "field_engineer"]},
    "menu.customers":    {"label": "菜单：客户管理",    "default_roles": ["admin", "pm"]},
    "menu.users":        {"label": "菜单：用户管理",    "default_roles": ["admin"]},
    "menu.groups":       {"label": "菜单：用户组管理",  "default_roles": ["admin"]},
    "menu.permissions":  {"label": "菜单：权限管理",    "default_roles": ["admin"]},
}


async def seed_default_permissions(db: AsyncSession) -> None:
    """Seed any missing permission rows. Incremental — safe to call on every startup."""
    result = await db.execute(select(RolePermission.permission_key, RolePermission.role))
    existing = {(r[0], r[1]) for r in result.all()}
    added = False
    for key, defn in PERMISSION_DEFS.items():
        for role in defn["default_roles"]:
            if (key, role) not in existing:
                db.add(RolePermission(permission_key=key, role=role))
                added = True
    if added:
        await db.commit()


class PermissionUpdate(BaseModel):
    roles: list[str]


@router.get("")
async def get_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(RolePermission))
    rows = result.scalars().all()
    by_key: dict[str, set[str]] = {k: set() for k in PERMISSION_DEFS}
    for r in rows:
        if r.permission_key in by_key:
            by_key[r.permission_key].add(r.role)
    return {
        "roles": ALL_ROLES,
        "role_labels": ROLE_LABELS,
        "permissions": [
            {"key": key, "label": defn["label"], "roles": sorted(by_key[key])}
            for key, defn in PERMISSION_DEFS.items()
        ],
    }


@router.put("/{perm_key}")
async def update_permission(
    perm_key: str,
    data: PermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission.manage")),
):
    if perm_key not in PERMISSION_DEFS:
        raise HTTPException(status_code=404, detail="权限项不存在")
    invalid = set(data.roles) - set(ALL_ROLES)
    if invalid:
        raise HTTPException(status_code=400, detail=f"无效角色: {', '.join(invalid)}")
    await db.execute(delete(RolePermission).where(RolePermission.permission_key == perm_key))
    for role in data.roles:
        db.add(RolePermission(permission_key=perm_key, role=role))
    await log_action(db, current_user.id, current_user.display_name, "permission_update",
                     "permission", None, perm_key, detail={"roles": data.roles})
    await db.commit()
    invalidate_perm_cache()
    return {"key": perm_key, "roles": data.roles}


@router.get("/me")
async def get_my_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RolePermission.permission_key).where(RolePermission.role == current_user.role)
    )
    return [r for (r,) in result.all()]


@router.post("/reset")
async def reset_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission.manage")),
):
    await db.execute(delete(RolePermission))
    for key, defn in PERMISSION_DEFS.items():
        for role in defn["default_roles"]:
            db.add(RolePermission(permission_key=key, role=role))
    await log_action(db, current_user.id, current_user.display_name, "permission_reset", "permission")
    await db.commit()
    invalidate_perm_cache()
    return {"detail": "已重置为默认权限"}
