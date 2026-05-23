from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.permissions import require_roles, require_permission
from app.models.project import Project, Customer
from app.models.task import Task, TaskDependency, TaskTransition
from app.models.suspension import ProjectSuspension
from app.models.notification import Notification
from app.models.comment import Comment
from app.models.attachment import Attachment
from app.models.escalation import TaskEscalation
from app.models.user import User
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    CustomerCreate, CustomerUpdate, CustomerResponse,
)
from app.schemas.task import TaskResponse
from app.services import project_service, template_service
from app.services.notification_service import notify
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _assert_pm_access(project: Project, current_user: User) -> None:
    """PM can only access projects assigned to them; unassigned projects are open to all PMs."""
    if current_user.role == "pm" and project.pm_id is not None and project.pm_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能管理自己负责的项目")


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("project.create")),
):
    customer = await db.get(Customer, data.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    project = await project_service.create_project(db, data, current_user.id)
    await db.flush()
    if project.pm_id and project.pm_id != current_user.id:
        await notify(
            db, project.pm_id, "project_assigned",
            f"新项目待立项: {project.name}",
            related_project_id=project.id,
        )
    await log_action(db, current_user.id, current_user.display_name, "create",
                     "project", project.id, project.name)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=dict)
async def list_projects(
    product_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sales_scope = current_user.id if current_user.role == "sales" else None
    pm_scope = current_user.id if current_user.role == "pm" else None
    items, total = await project_service.list_projects(db, product_type, status, search, page, page_size, sales_id=sales_scope, pm_scope_id=pm_scope)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [ProjectResponse.model_validate(p) for p in items],
    }


@router.get("/customers")
async def list_customers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func as _func
    result = await db.execute(
        select(
            Customer,
            _func.count(Project.id).label("project_count"),
        )
        .outerjoin(Project, Project.customer_id == Customer.id)
        .group_by(Customer.id)
        .order_by(Customer.id)
    )
    rows = result.all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "contact_name": c.contact_name,
            "contact_phone": c.contact_phone,
            "created_at": c.created_at,
            "project_count": pc,
        }
        for c, pc in rows
    ]


@router.post("/customers", response_model=CustomerResponse, status_code=201)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("project.create")),
):
    customer = await project_service.create_customer(db, data.name, data.contact_name, data.contact_phone)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.put("/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("project.create")),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.delete("/customers/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("project.delete")),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    proj_count = await db.execute(
        select(Project.id).where(Project.customer_id == customer_id).limit(1)
    )
    if proj_count.first():
        raise HTTPException(status_code=400, detail="该客户下存在项目，无法删除")
    await db.delete(customer)
    await db.commit()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pm_user = User.__table__.alias("pm_user")
    sales_user = User.__table__.alias("sales_user")
    result = await db.execute(
        select(
            Project,
            Customer.name.label("customer_name"),
            pm_user.c.display_name.label("pm_name"),
            sales_user.c.display_name.label("sales_name"),
        )
        .outerjoin(Customer, Project.customer_id == Customer.id)
        .outerjoin(pm_user, Project.pm_id == pm_user.c.id)
        .outerjoin(sales_user, Project.sales_id == sales_user.c.id)
        .where(Project.id == project_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    project, customer_name, pm_name, sales_name = row
    _assert_pm_access(project, current_user)
    d = {c.key: getattr(project, c.key) for c in Project.__table__.columns}
    d["customer_name"] = customer_name
    d["pm_name"] = pm_name
    d["sales_name"] = sales_name
    return ProjectResponse.model_validate(d)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role == "sales":
        if project.sales_id != current_user.id:
            raise HTTPException(status_code=403, detail="只能修改自己负责的项目")
        # Sales may only touch these fields
        SALES_ALLOWED = {"name", "planned_start", "planned_end", "description"}
        update_data = data.model_dump(exclude_none=True)
        forbidden = set(update_data.keys()) - SALES_ALLOWED
        if forbidden:
            raise HTTPException(status_code=403, detail=f"销售不能修改以下字段: {', '.join(forbidden)}")
    elif current_user.role not in ("pm", "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    else:
        _assert_pm_access(project, current_user)

    project = await project_service.update_project(db, project, data)
    await log_action(db, current_user.id, current_user.display_name, "update",
                     "project", project.id, project.name,
                     detail=data.model_dump(exclude_none=True))
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/init", response_model=list[TaskResponse])
async def init_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("project.initiate")),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _assert_pm_access(project, current_user)
    if project.status != "draft":
        raise HTTPException(status_code=400, detail="Project already initialized")
    tasks = await template_service.generate_tasks_from_template(db, project)
    if project.sales_id and project.sales_id != current_user.id:
        await notify(
            db, project.sales_id, "project_initiated",
            f"项目已立项启动: {project.name}，共生成 {len(tasks)} 个任务",
            related_project_id=project.id,
        )
    await log_action(db, current_user.id, current_user.display_name, "init",
                     "project", project.id, project.name,
                     detail={"task_count": len(tasks)})
    await db.commit()
    for t in tasks:
        await db.refresh(t)
    return tasks


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("project.delete")),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Collect task IDs for cascading deletes
    result = await db.execute(select(Task.id).where(Task.project_id == project_id))
    task_ids = [row[0] for row in result.all()]

    if task_ids:
        await db.execute(delete(TaskDependency).where(TaskDependency.task_id.in_(task_ids)))
        await db.execute(delete(TaskDependency).where(TaskDependency.depends_on_id.in_(task_ids)))
        await db.execute(delete(TaskTransition).where(TaskTransition.task_id.in_(task_ids)))
        await db.execute(delete(Comment).where(Comment.task_id.in_(task_ids)))
        await db.execute(delete(Attachment).where(Attachment.task_id.in_(task_ids)))
        await db.execute(delete(TaskEscalation).where(TaskEscalation.task_id.in_(task_ids)))
        await db.execute(delete(Notification).where(Notification.related_task_id.in_(task_ids)))
        await db.execute(delete(Task).where(Task.project_id == project_id))

    await db.execute(delete(ProjectSuspension).where(ProjectSuspension.project_id == project_id))
    await db.execute(delete(Notification).where(Notification.related_project_id == project_id))
    project_name = project.name
    await db.delete(project)
    await log_action(db, current_user.id, current_user.display_name, "delete",
                     "project", project_id, project_name)
    await db.commit()


from pydantic import BaseModel
from typing import Optional
from datetime import date as date_type


class SuspendRequest(BaseModel):
    reason_category: str
    reason: Optional[str] = None
    expected_resume: Optional[date_type] = None


class ResumeRequest(BaseModel):
    note: Optional[str] = None


@router.post("/{project_id}/suspend", response_model=ProjectResponse)
async def suspend_project(
    project_id: int,
    data: SuspendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("project.suspend")),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _assert_pm_access(project, current_user)
    if project.status != "active":
        raise HTTPException(status_code=400, detail="只有进行中的项目可以暂停")

    project.status = "suspended"
    await db.execute(
        update(Task)
        .where(Task.project_id == project_id, Task.status == "active")
        .values(status="paused")
    )
    suspension = ProjectSuspension(
        project_id=project_id,
        reason_category=data.reason_category,
        reason=data.reason,
        suspended_by=current_user.id,
        expected_resume=data.expected_resume,
    )
    db.add(suspension)
    await log_action(db, current_user.id, current_user.display_name, "suspend",
                     "project", project_id, project.name,
                     detail={"reason_category": data.reason_category, "reason": data.reason})
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/resume", response_model=ProjectResponse)
async def resume_project(
    project_id: int,
    data: ResumeRequest = ResumeRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("project.resume")),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _assert_pm_access(project, current_user)
    if project.status != "suspended":
        raise HTTPException(status_code=400, detail="只有暂停的项目可以恢复")

    project.status = "active"
    await db.execute(
        update(Task)
        .where(Task.project_id == project_id, Task.status == "paused")
        .values(status="active")
    )

    result = await db.execute(
        select(ProjectSuspension)
        .where(ProjectSuspension.project_id == project_id, ProjectSuspension.resumed_at == None)
        .order_by(ProjectSuspension.suspended_at.desc())
        .limit(1)
    )
    suspension = result.scalar_one_or_none()
    if suspension:
        now = datetime.utcnow()
        suspension.resumed_at = now
        suspension.resumed_by = current_user.id
        suspension.resume_note = data.note

        suspension_days = (now.date() - suspension.suspended_at.date()).days
        if suspension_days > 0:
            await db.execute(
                update(Task)
                .where(Task.project_id == project_id, Task.planned_end.is_not(None))
                .values(planned_end=Task.planned_end + timedelta(days=suspension_days))
            )
            if project.planned_end:
                project.planned_end = project.planned_end + timedelta(days=suspension_days)

    await log_action(db, current_user.id, current_user.display_name, "resume",
                     "project", project_id, project.name)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}/suspensions")
async def list_suspensions(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProjectSuspension)
        .where(ProjectSuspension.project_id == project_id)
        .order_by(ProjectSuspension.suspended_at.desc())
    )
    suspensions = result.scalars().all()
    return [
        {
            "id": s.id,
            "reason_category": s.reason_category,
            "reason": s.reason,
            "suspended_by": s.suspended_by,
            "suspended_at": s.suspended_at.isoformat() if s.suspended_at else None,
            "expected_resume": s.expected_resume.isoformat() if s.expected_resume else None,
            "resumed_at": s.resumed_at.isoformat() if s.resumed_at else None,
            "resumed_by": s.resumed_by,
            "resume_note": s.resume_note,
        }
        for s in suspensions
    ]
