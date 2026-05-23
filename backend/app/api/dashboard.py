from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.permissions import require_roles

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/my-workbench")
async def my_workbench(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(func.count()).select_from(Task).where(Task.assignee_id == current_user.id)

    pending = (await db.execute(base.where(Task.status == "pending"))).scalar() or 0
    active = (await db.execute(base.where(Task.status == "active"))).scalar() or 0
    review = (await db.execute(base.where(Task.status == "review"))).scalar() or 0
    done = (await db.execute(base.where(Task.status == "done"))).scalar() or 0
    overdue = (await db.execute(
        base.where(Task.status.in_(["active", "review"]), Task.planned_end < date.today())
    )).scalar() or 0

    return {
        "pending": pending,
        "active": active,
        "review": review,
        "done": done,
        "overdue": overdue,
        "total": pending + active + review + done,
    }


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_base = select(func.count()).select_from(Project)
    draft = (await db.execute(project_base.where(Project.status == "draft"))).scalar() or 0
    active = (await db.execute(project_base.where(Project.status == "active"))).scalar() or 0
    completed = (await db.execute(project_base.where(Project.status == "completed"))).scalar() or 0

    overdue_tasks = (await db.execute(
        select(func.count()).select_from(Task).where(
            Task.status.in_(["active", "review"]),
            Task.planned_end < date.today(),
        )
    )).scalar() or 0

    return {
        "projects": {"draft": draft, "active": active, "completed": completed},
        "overdue_tasks": overdue_tasks,
    }


@router.get("/phase-stats")
async def phase_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-phase task count grouped by status (for reports)."""
    result = await db.execute(
        select(Task.phase, Task.status, func.count()).group_by(Task.phase, Task.status)
    )
    rows = result.all()
    phases = {}
    for phase, status, count in rows:
        if phase not in phases:
            phases[phase] = {"total": 0, "done": 0, "active": 0, "pending": 0, "review": 0, "overdue": 0}
        phases[phase]["total"] += count
        if status in phases[phase]:
            phases[phase][status] += count
    # Count overdue per phase
    overdue_result = await db.execute(
        select(Task.phase, func.count()).where(
            Task.status.in_(["active", "review"]),
            Task.planned_end < date.today(),
        ).group_by(Task.phase)
    )
    for phase, count in overdue_result.all():
        if phase in phases:
            phases[phase]["overdue"] = count
    return phases


@router.get("/task-status-dist")
async def task_status_dist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Task count grouped by status, for pie chart."""
    result = await db.execute(
        select(Task.status, func.count()).group_by(Task.status)
    )
    return [{"status": s, "count": c} for s, c in result.all()]


@router.get("/product-type-dist")
async def product_type_dist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Project count grouped by product_type, for pie chart."""
    result = await db.execute(
        select(Project.product_type, func.count()).group_by(Project.product_type)
    )
    return [{"product_type": pt, "count": c} for pt, c in result.all()]


@router.get("/user-workload")
async def user_workload(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Active task count per user (for reports)."""
    result = await db.execute(
        select(User.id, User.display_name, User.role, func.count(Task.id))
        .join(Task, Task.assignee_id == User.id)
        .where(Task.status.in_(["active", "review"]))
        .group_by(User.id, User.display_name, User.role)
    )
    return [
        {"user_id": uid, "display_name": name, "role": role, "active_tasks": count}
        for uid, name, role, count in result.all()
    ]


@router.get("/delivery-cycle")
async def delivery_cycle(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Average actual dwell days per phase (tasks with both actual_start and actual_end)."""
    result = await db.execute(
        select(
            Task.phase,
            func.count(Task.id).label("sample_count"),
            func.avg(
                func.julianday(Task.actual_end) - func.julianday(Task.actual_start)
            ).label("avg_days"),
        )
        .where(Task.actual_start.is_not(None), Task.actual_end.is_not(None))
        .group_by(Task.phase)
    )
    return [
        {
            "phase": phase,
            "sample_count": count,
            "avg_days": round(avg_days, 1) if avg_days is not None else 0,
        }
        for phase, count, avg_days in result.all()
    ]


@router.get("/return-rate")
async def return_rate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rework (rejection) rate per phase."""
    result = await db.execute(
        select(
            Task.phase,
            func.count(Task.id).label("total"),
            func.sum(case((Task.rework_count > 0, 1), else_=0)).label("reworked"),
            func.avg(Task.rework_count).label("avg_rework"),
        )
        .group_by(Task.phase)
    )
    return [
        {
            "phase": phase,
            "total": total,
            "reworked": int(reworked or 0),
            "avg_rework": round(float(avg_rework or 0), 2),
            "rate": round(int(reworked or 0) / total * 100, 1) if total else 0,
        }
        for phase, total, reworked, avg_rework in result.all()
    ]


@router.post("/trigger-overdue-check")
async def trigger_overdue_check(
    current_user: User = Depends(require_roles("admin")),
):
    """Manually trigger overdue task check (admin only, for testing)."""
    from app.services.scheduler import check_overdue_tasks
    await check_overdue_tasks()
    return {"detail": "超期检测已执行，请查看通知"}
