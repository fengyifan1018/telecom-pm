from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.permissions import require_roles, require_permission
from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskResponse, TaskUpdate, TaskAssign, TaskAction,
    TaskTransitionResponse, CommentCreate, CommentResponse,
)
from app.services import task_service
from app.services.flow_engine import FlowEngine
from app.services.notification_service import notify
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    project_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
    phase: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scope = current_user.id if current_user.role in ("procurement", "field_engineer") else None
    sales_scope_ids: list[int] | None = None
    if current_user.role == "sales":
        from sqlalchemy import select as _select
        from app.models.project import Project as _Project
        res = await db.execute(_select(_Project.id).where(_Project.sales_id == current_user.id))
        sales_scope_ids = [r[0] for r in res.all()]
    items, total = await task_service.list_tasks(
        db, project_id, assignee_id, status, phase, page, page_size,
        scope_assignee_id=scope,
        sales_project_ids=sales_scope_ids,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


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
