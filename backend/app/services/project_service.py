from datetime import date, datetime

from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Customer
from app.models.task import Task
from app.models.escalation import TaskEscalation
from app.models.user import User
from app.models.workflow_template import WorkflowTemplate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.timeutil import now_cn


async def generate_project_no(db: AsyncSession) -> str:
    year = now_cn().year
    result = await db.execute(
        select(func.count()).where(Project.project_no.like(f"PRJ-{year}-%"))
    )
    count = result.scalar() or 0
    return f"PRJ-{year}-{count + 1:04d}"


async def create_project(db: AsyncSession, data: ProjectCreate, sales_id: int) -> Project:
    project_no = await generate_project_no(db)
    project = Project(
        project_no=project_no,
        name=data.name,
        customer_id=data.customer_id,
        product_type=data.product_type,
        priority=data.priority,
        sales_id=sales_id,
        pm_id=data.pm_id,
        planned_start=data.planned_start,
        planned_end=data.planned_end,
        description=data.description,
    )
    db.add(project)
    await db.flush()
    return project


async def list_projects(
    db: AsyncSession,
    product_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sales_id: int | None = None,
    pm_scope_id: int | None = None,  # scope: PM only sees own + unassigned projects
    delayed: bool = False,
    at_risk: bool = False,
    in_acceptance: bool = False,
) -> tuple[list[dict], int]:
    pm_user = User.__table__.alias("pm_user")
    sales_user = User.__table__.alias("sales_user")
    query = (
        select(
            Project,
            Customer.name.label("customer_name"),
            pm_user.c.display_name.label("pm_name"),
            sales_user.c.display_name.label("sales_name"),
        )
        .outerjoin(Customer, Project.customer_id == Customer.id)
        .outerjoin(pm_user, Project.pm_id == pm_user.c.id)
        .outerjoin(sales_user, Project.sales_id == sales_user.c.id)
    )
    count_query = select(func.count()).select_from(Project)

    today = date.today()
    conditions = []
    if pm_scope_id:
        conditions.append((Project.pm_id == pm_scope_id) | (Project.pm_id == None))
    if sales_id:
        conditions.append(Project.sales_id == sales_id)
    if product_type:
        conditions.append(Project.product_type == product_type)
    if status:
        conditions.append(Project.status == status)
    if search:
        like = f"%{search}%"
        conditions.append(Project.name.ilike(like) | Project.project_no.ilike(like))
    # 延期：计划结束已过且项目未完结
    if delayed:
        conditions.append(and_(Project.planned_end < today, Project.status.notin_(["completed", "cancelled"])))
    # 有风险：存在超期任务或未解决问题升级
    if at_risk:
        overdue_exists = select(Task.id).where(
            Task.project_id == Project.id,
            Task.planned_end < today,
            Task.status.notin_(["done", "cancelled"]),
        ).exists()
        escalation_exists = (
            select(TaskEscalation.id)
            .join(Task, Task.id == TaskEscalation.task_id)
            .where(Task.project_id == Project.id, TaskEscalation.status == "open")
            .exists()
        )
        conditions.append(overdue_exists | escalation_exists)
    # 验收中：项目进行中且模板验收阶段（倒数第二阶段）已激活
    if in_acceptance:
        templates = (
            await db.execute(select(WorkflowTemplate).where(WorkflowTemplate.is_active == True))
        ).scalars().all()
        acc_conds = []
        for tpl in templates:
            if len(tpl.phases) >= 2:
                acc_key = tpl.phases[-2]["phase"]
                acc_conds.append(and_(
                    Project.product_type == tpl.product_type,
                    Project.status == "active",
                    select(Task.id).where(
                        Task.project_id == Project.id,
                        Task.phase == acc_key,
                        Task.status.in_(["active", "review", "done"]),
                    ).exists(),
                ))
        conditions.append(or_(*acc_conds) if acc_conds else False)

    for cond in conditions:
        query = query.where(cond)
        count_query = count_query.where(cond)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = []
    for project, customer_name, pm_name, sales_name in result.all():
        d = {c.key: getattr(project, c.key) for c in Project.__table__.columns}
        d["customer_name"] = customer_name
        d["pm_name"] = pm_name
        d["sales_name"] = sales_name
        items.append(d)

    # 附加项目健康度聚合（仅当前页）
    if items:
        proj_ids = [d["id"] for d in items]
        agg = {pid: {"total": 0, "done": 0, "overdue": 0, "esc": 0} for pid in proj_ids}
        task_rows = await db.execute(
            select(
                Task.project_id,
                func.count(Task.id),
                func.sum(case((Task.status == "done", 1), else_=0)),
                func.sum(case((and_(Task.planned_end < today, Task.status.notin_(["done", "cancelled"])), 1), else_=0)),
            )
            .where(Task.project_id.in_(proj_ids))
            .group_by(Task.project_id)
        )
        for pid, total, done, overdue in task_rows.all():
            agg[pid] = {"total": total or 0, "done": done or 0, "overdue": overdue or 0, "esc": agg[pid]["esc"]}
        esc_rows = await db.execute(
            select(Task.project_id, func.count(TaskEscalation.id))
            .join(Task, Task.id == TaskEscalation.task_id)
            .where(Task.project_id.in_(proj_ids), TaskEscalation.status == "open")
            .group_by(Task.project_id)
        )
        for pid, cnt in esc_rows.all():
            agg[pid]["esc"] = cnt
        # 验收阶段激活标记
        templates = (
            await db.execute(select(WorkflowTemplate).where(WorkflowTemplate.is_active == True))
        ).scalars().all()
        acc_keys = {tpl.product_type: tpl.phases[-2]["phase"] for tpl in templates if len(tpl.phases) >= 2}
        acc_ids: set[int] = set()
        if acc_keys:
            acc_rows = await db.execute(
                select(Task.project_id, Task.phase).where(
                    Task.project_id.in_(proj_ids),
                    Task.status.in_(["active", "review", "done"]),
                    Task.phase.in_(set(acc_keys.values())),
                ).distinct()
            )
            for pid, phase in acc_rows.all():
                if acc_keys.get(dict((d["id"], d["product_type"]) for d in items).get(pid)) == phase:
                    acc_ids.add(pid)
        for d in items:
            a = agg[d["id"]]
            total_tasks = a["total"]
            d["task_total"] = total_tasks
            d["task_done"] = a["done"]
            d["progress_pct"] = round(a["done"] / total_tasks * 100) if total_tasks else 0
            d["overdue_count"] = a["overdue"]
            d["open_escalations"] = a["esc"]
            planned_end = d.get("planned_end")
            d["is_delayed"] = bool(planned_end and planned_end < today and d["status"] not in ("completed", "cancelled"))
            d["at_risk"] = a["overdue"] > 0 or a["esc"] > 0
            d["in_acceptance"] = d["status"] == "active" and d["id"] in acc_ids
    return items, total


async def update_project(db: AsyncSession, project: Project, data: ProjectUpdate) -> Project:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.version += 1
    project.updated_at = now_cn()
    return project


async def create_customer(db: AsyncSession, name: str, contact_name: str | None = None, contact_phone: str | None = None) -> Customer:
    customer = Customer(name=name, contact_name=contact_name, contact_phone=contact_phone)
    db.add(customer)
    await db.flush()
    return customer
