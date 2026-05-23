from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Customer
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate


async def generate_project_no(db: AsyncSession) -> str:
    year = datetime.utcnow().year
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
    return items, total


async def update_project(db: AsyncSession, project: Project, data: ProjectUpdate) -> Project:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.version += 1
    project.updated_at = datetime.utcnow()
    return project


async def create_customer(db: AsyncSession, name: str, contact_name: str | None = None, contact_phone: str | None = None) -> Customer:
    customer = Customer(name=name, contact_name=contact_name, contact_phone=contact_phone)
    db.add(customer)
    await db.flush()
    return customer
