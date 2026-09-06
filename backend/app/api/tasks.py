from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.permissions import require_roles, require_permission
from app.models.task import Task, TaskRelation, TaskWatcher
from app.models.project import Project
from app.models.user import User
from app.schemas.task import (
    TaskResponse, TaskUpdate, TaskAssign, TaskAction,
    TaskTransitionResponse, CommentCreate, CommentResponse, RelationCreate, BatchTaskUpdate,
)
from app.services import task_service
from app.services.flow_engine import FlowEngine
from app.services.notification_service import notify, notify_mentions, notify_watchers
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    project_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
    phase: str | None = None,
    keyword: str | None = None,
    priority: int | None = None,
    overdue: bool = False,
    sort: str | None = None,
    order: str = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scope_assignee_id, scoped_project_ids = await task_service.compute_task_scope(db, current_user)
    items, total = await task_service.list_tasks(
        db, project_id, assignee_id, status, phase, page, page_size,
        scope_assignee_id=scope_assignee_id,
        scoped_project_ids=scoped_project_ids,
        keyword=keyword,
        priority=priority,
        overdue=overdue,
        sort=sort,
        order=order,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


async def _get_visible_task(db: AsyncSession, task_id: int, current_user: User) -> Task:
    """取任务并校验数据范围；不存在或越权一律 404（不泄露存在性）。"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    scope_assignee_id, scoped_project_ids = await task_service.compute_task_scope(db, current_user)
    if not task_service.is_task_visible(task, scope_assignee_id, scoped_project_ids):
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_visible_task(db, task_id, current_user)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_visible_task(db, task_id, current_user)
    old_end = task.planned_end
    # exclude_unset：允许把 auto_schedule 置为 False（exclude_none 会丢掉 False 值）
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    rescheduled = 0
    if task.planned_end != old_end:
        from app.services import schedule_service
        rescheduled = await schedule_service.propagate(db, task, old_end, task.planned_end)
    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task).model_copy(update={"rescheduled": rescheduled})


@router.post("/batch-update")
async def batch_update_tasks(
    data: BatchTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("task.assign")),
):
    """批量更新任务：指派 / 优先级 / 截止日（PM/管理员的高频派单操作）。部分失败不影响其余任务。"""
    from app.services import schedule_service

    updates = data.model_dump(exclude_unset=True)
    task_ids = updates.pop("task_ids")
    if not updates:
        raise HTTPException(status_code=400, detail="未提供任何更新字段")

    updated: list[int] = []
    failed: list[dict] = []
    for tid in task_ids:
        task = await db.get(Task, tid)
        if not task:
            failed.append({"task_id": tid, "reason": "任务不存在"})
            continue
        old_end = task.planned_end
        for field, value in updates.items():
            setattr(task, field, value)
        # 截止日变化走排期联动（与单任务更新口径一致）
        if "planned_end" in updates and task.planned_end != old_end:
            await schedule_service.propagate(db, task, old_end, task.planned_end)
        if "assignee_id" in updates and task.assignee_id:
            await notify(
                db, task.assignee_id, "task_assigned",
                f"你被指派了任务: {task.title}",
                related_task_id=task.id, related_project_id=task.project_id,
            )
        updated.append(tid)

    if updated:
        await log_action(db, current_user.id, current_user.display_name, "batch_update",
                         "task", None, f"{len(updated)} 个任务",
                         detail={"fields": sorted(updates.keys()), "task_ids": updated})
    await db.commit()
    return {"updated": len(updated), "task_ids": updated, "failed": failed}


@router.put("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: int,
    data: TaskAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("task.assign")),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.assignee_id = data.assignee_id
    if data.reviewer_id:
        task.reviewer_id = data.reviewer_id
    await notify(
        db,
        user_id=data.assignee_id,
        type="task_assigned",
        title=f"你被指派了任务: {task.title}",
        related_task_id=task.id,
        related_project_id=task.project_id,
    )
    await notify_watchers(db, task, [current_user.id, data.assignee_id],
                          "task_assigned", f"你关注的任务已更新指派: {task.title}")
    await log_action(db, current_user.id, current_user.display_name, "assign",
                     "task", task.id, task.title,
                     detail={"assignee_id": data.assignee_id})
    await db.commit()
    await db.refresh(task)
    return task


@router.put("/{task_id}/start", response_model=TaskResponse)
async def start_task(
    task_id: int,
    data: TaskAction = TaskAction(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assignee_id != current_user.id and current_user.role not in ("pm", "admin"):
        raise HTTPException(status_code=403, detail="只有负责人或项目经理可以开始任务")
    # Auto-fill planned dates if not set
    if not task.planned_start or not task.planned_end:
        today = date.today()
        task.planned_start = today
        task.planned_end = today + timedelta(days=task.estimated_days)
    engine = FlowEngine(db)
    try:
        task = await engine.transition_task(task, "activate", current_user.id, data.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await db.refresh(task)
    return task


@router.put("/{task_id}/submit", response_model=TaskResponse)
async def submit_task(
    task_id: int,
    data: TaskAction = TaskAction(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assignee_id != current_user.id and current_user.role not in ("pm", "admin"):
        raise HTTPException(status_code=403, detail="只有负责人可以提交任务")
    engine = FlowEngine(db)
    try:
        task = await engine.transition_task(task, "submit", current_user.id, data.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if task.reviewer_id:
        await notify(db, task.reviewer_id, "task_status", f"任务待审核: {task.title}", related_task_id=task.id, related_project_id=task.project_id)
    await notify_watchers(db, task, [current_user.id] + ([task.reviewer_id] if task.reviewer_id else []),
                          "task_status", f"任务待审核: {task.title}")
    await log_action(db, current_user.id, current_user.display_name, "submit",
                     "task", task.id, task.title)
    await db.commit()
    await db.refresh(task)
    return task


@router.put("/{task_id}/approve", response_model=TaskResponse)
async def approve_task(
    task_id: int,
    data: TaskAction = TaskAction(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.reviewer_id != current_user.id and current_user.role not in ("pm", "admin"):
        raise HTTPException(status_code=403, detail="只有审核人或管理员可以审批")
    engine = FlowEngine(db)
    try:
        task = await engine.transition_task(task, "approve", current_user.id, data.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if task.assignee_id:
        await notify(db, task.assignee_id, "task_status", f"任务已通过: {task.title}", related_task_id=task.id, related_project_id=task.project_id)
    await notify_watchers(db, task, [current_user.id] + ([task.assignee_id] if task.assignee_id else []),
                          "task_status", f"任务已通过: {task.title}")
    await log_action(db, current_user.id, current_user.display_name, "approve",
                     "task", task.id, task.title)
    await db.commit()
    await db.refresh(task)
    return task


@router.put("/{task_id}/reject", response_model=TaskResponse)
async def reject_task(
    task_id: int,
    data: TaskAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.reviewer_id != current_user.id and current_user.role not in ("pm", "admin"):
        raise HTTPException(status_code=403, detail="只有审核人或管理员可以退回")
    if not data.remark:
        raise HTTPException(status_code=400, detail="Remark is required when rejecting")
    engine = FlowEngine(db)
    try:
        task = await engine.transition_task(task, "reject", current_user.id, data.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if task.assignee_id:
        await notify(db, task.assignee_id, "task_status", f"任务被退回: {task.title}", content=data.remark, related_task_id=task.id, related_project_id=task.project_id)
    await notify_watchers(db, task, [current_user.id] + ([task.assignee_id] if task.assignee_id else []),
                          "task_status", f"任务被退回: {task.title}", content=data.remark)
    await log_action(db, current_user.id, current_user.display_name, "reject",
                     "task", task.id, task.title,
                     detail={"remark": data.remark})
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/{task_id}/transitions")
async def get_transitions(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await task_service.get_task_transitions(db, task_id)


async def _relation_summary(db: AsyncSession, relation: TaskRelation, other_task_id: int) -> dict:
    """关系条目摘要（另一端任务 + 所属项目名）。"""
    other = await db.get(Task, other_task_id)
    project = await db.get(Project, other.project_id) if other else None
    return {
        "relation_id": relation.id,
        "relation_type": relation.relation_type,
        "task_id": other_task_id,
        "task_no": other.task_no if other else "",
        "title": other.title if other else "",
        "status": other.status if other else "",
        "project_name": project.name if project else "",
    }


@router.get("/{task_id}/relations")
async def get_relations(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    async def edges(where_column, value):
        result = await db.execute(
            select(TaskRelation).where(where_column == value, TaskRelation.relation_type.in_(["precedes", "blocks"]))
        )
        return result.scalars().all()

    groups = {"predecessors": [], "successors": [], "blocking": [], "blocked": []}
    for rel in await edges(TaskRelation.to_task_id, task_id):  # 指向我的边
        if rel.relation_type == "precedes":
            groups["predecessors"].append(await _relation_summary(db, rel, rel.from_task_id))
        else:
            groups["blocking"].append(await _relation_summary(db, rel, rel.from_task_id))
    for rel in await edges(TaskRelation.from_task_id, task_id):  # 我指出的边
        if rel.relation_type == "precedes":
            groups["successors"].append(await _relation_summary(db, rel, rel.to_task_id))
        else:
            groups["blocked"].append(await _relation_summary(db, rel, rel.to_task_id))
    return groups


@router.post("/{task_id}/relations", status_code=201)
async def create_relation(
    task_id: int,
    data: RelationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if current_user.role not in ("pm", "admin") and task.assignee_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有负责人或项目经理可以维护任务关系")
    related = await db.get(Task, data.related_task_id)
    if not related:
        raise HTTPException(status_code=404, detail="Related task not found")
    if related.id == task.id:
        raise HTTPException(status_code=400, detail="不能与任务自身建立关系")

    # in：related 指向当前任务；out：当前任务指向 related
    if data.direction == "in":
        from_tid, to_tid = related.id, task.id
    else:
        from_tid, to_tid = task.id, related.id

    dup = await db.execute(
        select(TaskRelation).where(
            TaskRelation.from_task_id == from_tid,
            TaskRelation.to_task_id == to_tid,
            TaskRelation.relation_type == data.relation_type,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="关系已存在")

    if data.relation_type == "precedes":
        # 成环检测：沿 precedes 出边从 to 出发，若能回到 from 则成环
        seen, stack = set(), [to_tid]
        while stack:
            cur = stack.pop()
            if cur == from_tid:
                raise HTTPException(status_code=400, detail="不能建立关系：存在循环依赖")
            if cur in seen or len(seen) > 500:
                continue
            seen.add(cur)
            res = await db.execute(
                select(TaskRelation.to_task_id).where(
                    TaskRelation.relation_type == "precedes",
                    TaskRelation.from_task_id == cur,
                )
            )
            stack.extend(r[0] for r in res.all())

    rel = TaskRelation(
        from_task_id=from_tid, to_task_id=to_tid,
        relation_type=data.relation_type, created_by=current_user.id,
    )
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    return {"relation_id": rel.id, "relation_type": rel.relation_type,
            "from_task_id": rel.from_task_id, "to_task_id": rel.to_task_id}


@router.delete("/relations/{relation_id}", status_code=204)
async def delete_relation(
    relation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rel = await db.get(TaskRelation, relation_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Relation not found")
    if current_user.role not in ("pm", "admin") and rel.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只有创建者或项目经理可以删除关系")
    await db.delete(rel)
    await db.commit()


@router.get("/{task_id}/watch")
async def get_watch(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_visible_task(db, task_id, current_user)
    rows = await db.execute(
        select(User.id, User.display_name)
        .join(TaskWatcher, TaskWatcher.user_id == User.id)
        .where(TaskWatcher.task_id == task_id)
        .order_by(TaskWatcher.created_at)
    )
    watchers = [{"id": uid, "display_name": name} for uid, name in rows.all()]
    return {"watching": any(w["id"] == current_user.id for w in watchers), "count": len(watchers), "watchers": watchers}


@router.put("/{task_id}/watch")
async def toggle_watch(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_visible_task(db, task_id, current_user)
    existing = await db.execute(
        select(TaskWatcher).where(TaskWatcher.task_id == task_id, TaskWatcher.user_id == current_user.id)
    )
    cur = existing.scalar_one_or_none()
    if cur:
        await db.delete(cur)
        watching = False
    else:
        db.add(TaskWatcher(task_id=task_id, user_id=current_user.id))
        watching = True
    await db.commit()
    return {"watching": watching}


@router.post("/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def add_comment(
    task_id: int,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    comment = await task_service.add_comment(db, task_id, current_user.id, data.content)
    await db.commit()
    await db.refresh(comment)
    await notify_mentions(
        db, data.content, current_user.id, task.title,
        related_task_id=task.id, related_project_id=task.project_id,
    )
    await db.commit()
    return comment


@router.get("/{task_id}/comments")
async def get_comments(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await task_service.get_task_comments(db, task_id)
