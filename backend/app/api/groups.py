from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.user_group import UserGroup, UserGroupMember
from app.permissions import require_permission

router = APIRouter(prefix="/api/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class MemberAdd(BaseModel):
    user_id: int


@router.get("")
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            UserGroup.id,
            UserGroup.name,
            UserGroup.description,
            UserGroup.created_at,
            func.count(UserGroupMember.id).label("member_count"),
        )
        .outerjoin(UserGroupMember, UserGroupMember.group_id == UserGroup.id)
        .group_by(UserGroup.id)
        .order_by(UserGroup.id)
    )
    rows = result.all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "created_at": r.created_at,
            "member_count": r.member_count,
        }
        for r in rows
    ]


@router.post("", status_code=201)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group.manage")),
):
    existing = await db.execute(select(UserGroup).where(UserGroup.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户组名称已存在")
    group = UserGroup(name=data.name, description=data.description)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return {"id": group.id, "name": group.name, "description": group.description, "created_at": group.created_at, "member_count": 0}


@router.put("/{group_id}")
async def update_group(
    group_id: int,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group.manage")),
):
    group = await db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")
    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group.manage")),
):
    group = await db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")
    await db.delete(group)
    await db.commit()


@router.get("/{group_id}/members")
async def list_members(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = await db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")
    result = await db.execute(
        select(User.id, User.username, User.display_name, User.role, User.is_active)
        .join(UserGroupMember, UserGroupMember.user_id == User.id)
        .where(UserGroupMember.group_id == group_id)
        .order_by(User.id)
    )
    rows = result.all()
    return [
        {"id": r.id, "username": r.username, "display_name": r.display_name, "role": r.role, "is_active": r.is_active}
        for r in rows
    ]


@router.post("/{group_id}/members", status_code=201)
async def add_member(
    group_id: int,
    data: MemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group.manage")),
):
    group = await db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")
    user = await db.get(User, data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    existing = await db.execute(
        select(UserGroupMember).where(
            UserGroupMember.group_id == group_id,
            UserGroupMember.user_id == data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该用户已在组内")
    db.add(UserGroupMember(group_id=group_id, user_id=data.user_id))
    await db.commit()
    return {"ok": True}


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group.manage")),
):
    result = await db.execute(
        select(UserGroupMember).where(
            UserGroupMember.group_id == group_id,
            UserGroupMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    await db.delete(member)
    await db.commit()
