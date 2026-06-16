import re
from datetime import date

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskTransition
from app.models.project import Project
from app.models.comment import Comment
from app.models.user import User
from app.services.notification_service import notify


SORT_FIELDS = {
    "planned_end": Task.planned_end,
    "priority": Task.priority,
    "created_at": Task.created_at,
}

# 任务可见性范围策略：
# - 工程/执行角色按"指派给自己"看
# - 销售/项目经理按"自己负责的项目"看
# - 其余角色（admin、operations）不受限（operations 为只读全局可见）
ASSIGNEE_SCOPED_ROLES = ("procurement", "field_engineer", "network_engineer")
PROJECT_SCOPED_ROLES = ("sales", "pm")


async def compute_task_scope(db: AsyncSession, user: User) -> tuple[int | None, list[int] | None]:
    """返回 (scope_assignee_id, scoped_project_ids)，限定 user 可见的任务范围。
    两者均为 None 表示不受限（admin / operations）。"""
    if user.role in ASSIGNEE_SCOPED_ROLES:
        return user.id, None
    if user.role in PROJECT_SCOPED_ROLES:
        col = Project.sales_id if user.role == "sales" else Project.pm_id
        res = await db.execute(select(Project.id).where(col == user.id))
        return None, [r[0] for r in res.all()]
    return None, None


def is_task_visible(task: Task, scope_assignee_id: int | None, scoped_project_ids: list[int] | None) -> bool:
    """单任务可见性判断，与 compute_task_scope 的范围一致。"""
    if scope_assignee_id is not None:
        return task.assignee_id == scope_assignee_id
    if scoped_project_ids is not None:
        return task.project_id in scoped_project_ids
    return True


async def list_tasks(
    db: AsyncSession,
    project_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
    phase: str | None = None,
    page: int = 1,
    page_size: int = 50,
    scope_assignee_id: int | None = None,  # scope: 工程/执行角色只看指派给自己的任务
    scoped_project_ids: list[int] | None = None,  # scope: 销售/PM 只看自己负责项目的任务
    keyword: str | None = None,
    priority: int | None = None,
    overdue: bool = False,
    sort: str | None = None,
    order: str = "asc",
) -> tuple[list[dict], int]:
    assignee = User.__table__.alias("assignee")
    project = Project.__table__.alias("project")
    query = (
        select(
            Task,
            assignee.c.display_name.label("assignee_name"),
            project.c.name.label("project_name"),
        )
        .outerjoin(assignee, Task.assignee_id == assignee.c.id)
        .outerjoin(project, Task.project_id == project.c.id)
    )
    count_query = select(func.count()).select_from(Task)

    conditions = []
    if scoped_project_ids is not None:
        if scoped_project_ids:
            conditions.append(Task.project_id.in_(scoped_project_ids))
        else:
            conditions.append(Task.project_id == -1)  # no projects → no tasks
    if scope_assignee_id:
        conditions.append(Task.assignee_id == scope_assignee_id)
    elif assignee_id:
        conditions.append(Task.assignee_id == assignee_id)
    if project_id:
        conditions.append(Task.project_id == project_id)
    if status:
        statuses = [s for s in status.split(",") if s]
        if len(statuses) > 1:
            conditions.append(Task.status.in_(statuses))
        elif statuses:
            conditions.append(Task.status == statuses[0])
    if phase:
        conditions.append(Task.phase == phase)
    if keyword:
        kw = f"%{keyword}%"
        conditions.append(or_(Task.title.like(kw), Task.task_no.like(kw)))
    if priority:
        conditions.append(Task.priority == priority)
    if overdue:
        conditions.append(Task.planned_end < date.today())
        conditions.append(Task.status.notin_(["done", "cancelled"]))

    for cond in conditions:
        query = query.where(cond)
        count_query = count_query.where(cond)

    total = (await db.execute(count_query)).scalar() or 0

    sort_col = SORT_FIELDS.get(sort)
    if sort_col is not None:
        query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    else:
        query = query.order_by(Task.id)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = []
    for task, assignee_name, project_name in result.all():
        d = {
            "id": task.id,
            "project_id": task.project_id,
            "project_name": project_name,
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
