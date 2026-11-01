from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.permissions import require_roles, require_permission
from app.models.user import User
from app.models.task import Task
from app.schemas.auth import UserResponse, UserCreate, UserUpdate, ChangePassword
from app.seed.seed_users import hash_password, verify_password
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    role: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(User).where(User.is_active == True)
    if role:
        query = query.where(User.role == role)
    result = await db.execute(query.order_by(User.id))
    return result.scalars().all()


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
    )
    db.add(user)
    await log_action(db, current_user.id, current_user.display_name, "create",
                     "user", None, data.display_name)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/wecom-bind-requests")
async def list_wecom_bind_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
):
    """企微账号待绑定候选（成员给机器人发消息产生，未指认）。"""
    from app.models.wecom_bind import WecomBindRequest
    rows = await db.execute(
        select(WecomBindRequest)
        .where(WecomBindRequest.bound_user_id.is_(None))
        .order_by(WecomBindRequest.last_at.desc())
    )
    return [
        {"id": r.id, "wecom_userid": r.wecom_userid, "last_content": r.last_content, "last_at": r.last_at}
        for r in rows.scalars().all()
    ]


@router.post("/{user_id}/bind-wecom")
async def bind_wecom_userid(
    user_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
):
    """管理员将待绑定候选的企微账号指认绑定到系统用户。"""
    from app.models.wecom_bind import WecomBindRequest
    wxid = (data.get("wecom_userid") or "").strip()
    if not wxid:
        raise HTTPException(status_code=400, detail="wecom_userid 不能为空")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 冲突校验：企微账号未占用 / 用户未绑定
    dup_wx = await db.execute(
        select(WecomBindRequest).where(WecomBindRequest.wecom_userid == wxid, WecomBindRequest.bound_user_id.is_not(None))
    )
    if dup_wx.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该企微账号已绑定其他用户")
    if user.wecom_userid:
        raise HTTPException(status_code=400, detail="该用户已绑定企微账号")
    # 标记候选为已绑定（若存在）
    cand = await db.execute(
        select(WecomBindRequest).where(WecomBindRequest.wecom_userid == wxid)
    )
    cand_row = cand.scalar_one_or_none()
    if cand_row is None:
        cand_row = WecomBindRequest(wecom_userid=wxid)
        db.add(cand_row)
    cand_row.bound_user_id = user.id
    user.wecom_userid = wxid
    await log_action(db, current_user.id, current_user.display_name, "bind_wecom",
                     "user", user.id, user.display_name, detail={"wecom_userid": wxid})
    await db.commit()
    return {"detail": "已绑定", "wecom_userid": wxid}


@router.get("/{user_id}/workload")
async def get_user_workload(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(func.count()).where(
            Task.assignee_id == user_id,
            Task.status.in_(["active", "review"]),
        )
    )
    active_tasks = result.scalar() or 0
    return {"active_tasks": active_tasks, "warning": active_tasks >= 3}


@router.put("/me/password")
async def change_password(
    data: ChangePassword,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return {"detail": "密码修改成功"}


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await log_action(db, current_user.id, current_user.display_name, "delete",
                     "user", user_id, user.display_name)
    await db.delete(user)
    await db.commit()


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await log_action(db, current_user.id, current_user.display_name, "update",
                     "user", user_id, user.display_name,
                     detail=data.model_dump(exclude_none=True))
    await db.commit()
    await db.refresh(user)
    return user
