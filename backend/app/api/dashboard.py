from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case, and_, or_, false
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.task import TaskTransition
from app.models.escalation import TaskEscalation
from app.permissions import require_roles

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


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
    # 平均进度（done 计 100），供报表加权展示
    avg_result = await db.execute(
        select(
            Task.phase,
            func.avg(case((Task.status == "done", 100), else_=Task.progress)),
        ).group_by(Task.phase)
    )
    for phase, avg in avg_result.all():
        if phase in phases:
            phases[phase]["avg_progress"] = round(float(avg or 0), 1)
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




@router.get("/workbench")
async def workbench(
    scope: str = "mine",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """工作台驾驶舱聚合：统计/健康分布/任务分布/风险/Top5/近期截止/动态，全部按角色可见范围过滤。"""
    from app.services.task_service import compute_task_scope

    today = date.today()
    uid = current_user.id
    scope_assignee_id, scoped_project_ids = await compute_task_scope(db, current_user)

    can_global = current_user.role in ("admin", "pm", "operations")
    effective = "all" if (scope == "all" and can_global) else "mine"

    # 任务范围条件：
    # - 全局视图：按角色可见口径（compute_task_scope）
    # - 我的视图：全局角色看指派给自己的；销售/执行角色按其角色口径（销售=自己项目任务，执行=指派）
    if effective == "all":
        task_conds = []
        if scope_assignee_id is not None:
            task_conds.append(Task.assignee_id == scope_assignee_id)
        elif scoped_project_ids is not None:
            task_conds.append(Task.project_id.in_(scoped_project_ids) if scoped_project_ids else false())
    elif can_global:
        task_conds = [Task.assignee_id == uid]
    else:
        if scope_assignee_id is not None:
            task_conds = [Task.assignee_id == scope_assignee_id]
        else:
            task_conds = [Task.project_id.in_(scoped_project_ids) if scoped_project_ids else false()]

    overdue_cond = and_(Task.planned_end < today, Task.status.notin_(["done", "cancelled"]))

    # ── 任务统计 ──
    status_rows = (await db.execute(
        select(Task.status, func.count()).where(*task_conds).group_by(Task.status)
    )).all()
    counts = {st: c for st, c in status_rows}
    task_total = sum(counts.values())
    task_done = counts.get("done", 0)
    task_active = counts.get("active", 0) + counts.get("review", 0)
    task_overdue = (await db.execute(
        select(func.count()).where(*task_conds, overdue_cond)
    )).scalar() or 0
    completion_pct = round(task_done / task_total * 100) if task_total else 0

    # ── 项目统计与可见集合（销售=自己的，PM=自己的，其余=全部）──
    if current_user.role == "sales":
        vis_ids = [r[0] for r in (await db.execute(select(Project.id).where(Project.sales_id == uid))).all()]
    elif current_user.role == "pm":
        vis_ids = [r[0] for r in (await db.execute(
            select(Project.id).where(or_(Project.pm_id == uid, Project.pm_id.is_(None)))
        )).all()]
    else:
        vis_ids = None
    vis_filter = [Project.id.in_(vis_ids)] if vis_ids is not None else []
    if vis_ids is not None and not vis_ids:
        vis_filter = [false()]

    pq = select(Project.status, func.count()).group_by(Project.status)
    for c in vis_filter:
        pq = pq.where(c)
    pc = {st: c for st, c in (await db.execute(pq)).all()}
    project_total = sum(pc.values())
    project_active = pc.get("active", 0)
    project_completed = pc.get("completed", 0)

    # ── 进行中项目健康桶（风险=有超期或未解决升级；延期=计划结束已过；其余=正常）──
    active_ids = [r[0] for r in (await db.execute(
        select(Project.id).where(Project.status == "active", *vis_filter)
    )).all()]
    overdue_by_project, esc_by_project = {}, {}
    if active_ids:
        rows = (await db.execute(
            select(Task.project_id, func.count()).where(
                Task.project_id.in_(active_ids), overdue_cond
            ).group_by(Task.project_id)
        )).all()
        overdue_by_project = {pid: c for pid, c in rows}
        rows = (await db.execute(
            select(Task.project_id, func.count(TaskEscalation.id))
            .join(Task, Task.id == TaskEscalation.task_id)
            .where(Task.project_id.in_(active_ids), TaskEscalation.status == "open")
            .group_by(Task.project_id)
        )).all()
        esc_by_project = {pid: c for pid, c in rows}
    delayed_ids = [r[0] for r in (await db.execute(
        select(Project.id).where(
            Project.status == "active", Project.planned_end < today, *vis_filter
        )
    )).all()]
    at_risk_ids = {pid for pid in active_ids if overdue_by_project.get(pid, 0) > 0 or esc_by_project.get(pid, 0) > 0}
    project_health = {
        "normal": len(active_ids) - len(at_risk_ids),
        "at_risk": len(at_risk_ids),
        "delayed": len(set(delayed_ids) - at_risk_ids),
        "completed": project_completed,
        "draft": pc.get("draft", 0),
    }

    # ── 在建项目 Top5（进行中，按截止日期升序）──
    top_projects = []
    if active_ids:
        prog_rows = (await db.execute(
            select(
                Task.project_id,
                func.count(Task.id),
                func.sum(case((Task.status == "done", 1), else_=0)),
            ).where(Task.project_id.in_(active_ids), Task.is_required == True).group_by(Task.project_id)
        )).all()
        prog = {pid: (total or 0, done or 0) for pid, total, done in prog_rows}
        delayed_set = set(delayed_ids)
        rows = (await db.execute(
            select(Project.id, Project.name, Project.planned_end)
            .where(Project.id.in_(active_ids))
            .order_by(Project.planned_end.is_(None), Project.planned_end)
            .limit(5)
        )).all()
        for pid, name, pend in rows:
            total, done = prog.get(pid, (0, 0))
            top_projects.append({
                "project_id": pid, "name": name,
                "progress_pct": round(done / total * 100) if total else 0,
                "planned_end": pend,
                "is_delayed": pid in delayed_set,
            })

    # ── 任务状态分布 ──
    task_status_dist = [{"status": st, "count": c} for st, c in counts.items()]

    # ── 风险预警：未解决升级 + 超期任务（可见范围内，严重度优先取 5）──
    risks = []
    esc_rows = (await db.execute(
        select(TaskEscalation, Task.id, Task.task_no, Task.title, Task.assignee_id, User.display_name)
        .join(Task, Task.id == TaskEscalation.task_id)
        .outerjoin(User, User.id == Task.assignee_id)
        .where(TaskEscalation.status == "open", *task_conds)
        .order_by(TaskEscalation.created_at.desc())
    )).all()
    for esc, tid, tno, title, aid, aname in esc_rows:
        risks.append({
            "kind": "escalation", "task_id": tid, "task_no": tno,
            "title": esc.description, "severity": esc.severity,
            "owner": aname or "-", "created_at": esc.created_at,
        })
    od_rows = (await db.execute(
        select(Task, User.display_name)
        .outerjoin(User, User.id == Task.assignee_id)
        .where(*task_conds, overdue_cond, Task.status.in_(["active", "review"]))
        .order_by(Task.planned_end)
        .limit(10)
    )).all()
    for t, aname in od_rows:
        days = (today - t.planned_end).days
        risks.append({
            "kind": "overdue", "task_id": t.id, "task_no": t.task_no,
            "title": f"{t.title}（超期 {days} 天）", "severity": "high" if days >= 3 else "medium",
            "owner": aname or "-", "created_at": t.updated_at,
        })
    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    risks.sort(key=lambda r: sev_rank.get(r["severity"], 9))
    risks = risks[:5]

    # ── 近期截止：未完成任务按截止升序取 5 ──
    due_rows = (await db.execute(
        select(Task.id, Task.title, Task.priority, Task.planned_end, Project.name)
        .join(Project, Project.id == Task.project_id)
        .where(*task_conds, Task.status.in_(["pending", "active", "review"]), Task.planned_end.is_not(None))
        .order_by(Task.planned_end)
        .limit(5)
    )).all()
    due_soon = [
        {"task_id": tid, "title": title, "priority": pri, "planned_end": pend, "project_name": pname}
        for tid, title, pri, pend, pname in due_rows
    ]

    # ── 最近动态：可见任务的流转记录 ──
    act_rows = (await db.execute(
        select(TaskTransition, Task.title, User.display_name)
        .join(Task, Task.id == TaskTransition.task_id)
        .join(User, User.id == TaskTransition.operator_id)
        .where(*task_conds)
        .order_by(TaskTransition.created_at.desc())
        .limit(8)
    )).all()
    activity = [
        {
            "task_id": tr.task_id, "task_title": title, "operator_name": operator,
            "from_status": tr.from_status, "to_status": tr.to_status, "created_at": tr.created_at,
        }
        for tr, title, operator in act_rows
    ]

    return {
        "scope": effective,
        "stats": {
            "project_total": project_total,
            "project_active": project_active,
            "project_completed": project_completed,
            "task_total": task_total,
            "task_done": task_done,
            "task_active": task_active,
            "task_overdue": task_overdue,
            "completion_pct": completion_pct,
        },
        "project_health": project_health,
        "task_status_dist": task_status_dist,
        "top_projects": top_projects,
        "risks": risks,
        "due_soon": due_soon,
        "activity": activity,
    }

@router.post("/trigger-overdue-check")
async def trigger_overdue_check(
    current_user: User = Depends(require_roles("admin")),
):
    """Manually trigger overdue task check (admin only, for testing)."""
    from app.services.scheduler import check_overdue_tasks
    await check_overdue_tasks()
    return {"detail": "超期检测已执行，请查看通知"}
