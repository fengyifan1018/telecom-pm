import re

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskTransition
from app.models.comment import Comment
from app.models.user import User
from app.services.notification_service import notify


async def list_tasks(
    db: AsyncSession,
    project_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
    phase: str | None = None,
    page: int = 1,
    page_size: int = 50,
    scope_assignee_id: int | None = None,  # scope: field/procurement only see own tasks
    sales_project_ids: list[int] | None = None,  # scope: sales only see own projects' tasks
) -> tuple[list[dict], int]:
    assignee = User.__table__.alias("assignee")
    query = select(Task, assignee.c.display_name.label("assignee_name")).outerjoin(
        assignee, Task.assignee_id == assignee.c.id
    )
    count_query = select(func.count()).select_from(Task)

    conditions = []
    if sales_project_ids is not None:
        if sales_project_ids:
            conditions.append(Task.project_id.in_(sales_project_ids))
        else:
            conditions.append(Task.project_id == -1)  # no projects → no tasks
    if scope_assignee_id:
        conditions.append(Task.assignee_id == scope_assignee_id)
    elif assignee_id:
        conditions.append(Task.assignee_id == assignee_id)
    if project_id:
        conditions.append(Task.project_id == project_id)
    if status:
        conditions.append(Task.status == status)
    if phase:
        conditions.append(Task.phase == phase)

    for cond in conditions:
        query = query.where(cond)
        count_query = count_query.where(cond)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Task.id).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = []
    for task, assignee_name in result.all():
        d = {
            "id": task.id,
            "project_id": task.project_id,
            "task_no": task.task_no,
            "title": task.title,
            "phase": task.phase,
            "status": task.status,
            "is_required": task.is_required,
            "assignee_id": task.assignee_id,
            "assignee_name": assignee_name,
            "reviewer_id": task.reviewer_id,
            "priority": task.priority,
            "planned_start": task.planned_start,
            "planned_end": task.planned_end,
            "actual_start": task.actual_start,
            "actual_end": task.actual_end,
            "rework_count": task.rework_count,
            "created_at": task.created_at,
        }
        items.append(d)
    return items, total


async def get_task_transitions(db: AsyncSession, task_id: int) -> list[dict]:
    result = await db.execute(
        select(TaskTransition, User.display_name)
        .join(User, TaskTransition.operator_id == User.id)
        .where(TaskTransition.task_id == task_id)
        .order_by(TaskTransition.created_at.desc())
    )
    return [
        {
            "id": t.id,
            "task_id": t.task_id,
            "from_status": t.from_status,
            "to_status": t.to_status,
            "operator_id": t.operator_id,
            "operator_name": name,
            "remark": t.remark,
            "created_at": t.created_at,
        }
        for t, name in result.all()
    ]


async def get_task_comments(db: AsyncSession, task_id: int) -> list[dict]:
    result = await db.execute(
        select(Comment, User.display_name)
        .join(User, Comment.user_id == User.id)
        .where(Comment.task_id == task_id)
        .order_by(Comment.created_at.asc())
    )
    return [
        {
            "id": c.id,
            "task_id": c.task_id,
            "user_id": c.user_id,
            "user_name": name,
            "content": c.content,
            "created_at": c.created_at,
        }
        for c, name in result.all()
    ]


async def add_comment(db: AsyncSession, task_id: int, user_id: int, content: str) -> Comment:
    comment = Comment(task_id=task_id, user_id=user_id, content=content)
    db.add(comment)
    await db.flush()

    mentions = set(re.findall(r'@(\S+)', content))
    if mentions:
        result = await db.execute(select(User).where(User.display_name.in_(mentions)))
        task = await db.get(Task, task_id)
        for u in result.scalars().all():
            if u.id != user_id:
                await notify(
                    db, u.id, "comment_mention",
                    f"在任务中被@提及",
                    content=content[:100],
                    related_task_id=task_id,
                    related_project_id=task.project_id if task else None,
                )

    return comment
