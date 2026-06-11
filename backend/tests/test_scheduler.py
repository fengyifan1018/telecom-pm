from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.notification import Notification
from app.services.scheduler import _run_checks


async def _make_user(db: AsyncSession, username: str, role: str, is_active: bool = True) -> User:
    user = User(username=username, hashed_password="x", display_name=username, role=role, is_active=is_active)
    db.add(user)
    await db.flush()
    return user


async def _make_task(db: AsyncSession, project_id: int, assignee_id: int, planned_end: date, status: str = "active") -> Task:
    task = Task(
        project_id=project_id,
        task_no=f"T-{assignee_id}-{planned_end.isoformat()}-{status}",
        title="测试任务",
        phase="survey",
        status=status,
        assignee_id=assignee_id,
        planned_end=planned_end,
    )
    db.add(task)
    await db.flush()
    return task


async def _notifs(db: AsyncSession, type: str | None = None) -> list[Notification]:
    q = select(Notification)
    if type:
        q = q.where(Notification.type == type)
    return list((await db.execute(q)).scalars().all())


async def _setup_actors(db: AsyncSession):
    """Create assignee, pm, ops, admin (+ an inactive ops) and a project owned by pm."""
    assignee = await _make_user(db, "field", "field_engineer")
    pm = await _make_user(db, "pm", "pm")
    ops = await _make_user(db, "ops", "operations")
    admin = await _make_user(db, "admin", "admin")
    await _make_user(db, "ops_inactive", "operations", is_active=False)
    project = Project(project_no="PRJ-T-0001", name="测试项目", customer_id=1,
                      product_type="dia", status="active", sales_id=assignee.id, pm_id=pm.id)
    db.add(project)
    await db.flush()
    return assignee, pm, ops, admin, project


async def test_overdue_1_day_notifies_only_assignee(db: AsyncSession):
    assignee, pm, ops, admin, project = await _setup_actors(db)
    await _make_task(db, project.id, assignee.id, date.today() - timedelta(days=1))

    sent = await _run_checks(db)

    overdue = await _notifs(db, "overdue")
    assert sent == 1
    assert {n.user_id for n in overdue} == {assignee.id}


async def test_overdue_5_days_escalates_to_pm_ops_admin(db: AsyncSession):
    assignee, pm, ops, admin, project = await _setup_actors(db)
    await _make_task(db, project.id, assignee.id, date.today() - timedelta(days=5))

    await _run_checks(db)

    recipients = {n.user_id for n in await _notifs(db, "overdue")}
    # assignee + pm + active ops + admin; inactive ops excluded
    assert recipients == {assignee.id, pm.id, ops.id, admin.id}


async def test_overdue_is_deduped_within_same_day(db: AsyncSession):
    assignee, pm, ops, admin, project = await _setup_actors(db)
    await _make_task(db, project.id, assignee.id, date.today() - timedelta(days=5))

    first = await _run_checks(db)
    await db.commit()
    second = await _run_checks(db)

    assert first == 4
    assert second == 0
    assert len(await _notifs(db, "overdue")) == 4


async def test_due_tomorrow_warns_assignee(db: AsyncSession):
    assignee, pm, ops, admin, project = await _setup_actors(db)
    await _make_task(db, project.id, assignee.id, date.today() + timedelta(days=1))

    sent = await _run_checks(db)

    due_soon = await _notifs(db, "due_soon")
    assert sent == 1
    assert len(due_soon) == 1
    assert due_soon[0].user_id == assignee.id
    assert await _notifs(db, "overdue") == []
