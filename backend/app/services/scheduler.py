"""Background scheduler: runs overdue escalation + upcoming-due checks periodically."""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.task import Task
from app.models.project import Project
from app.models.user import User
from app.models.notification import Notification
from app.services.notification_service import notify

logger = logging.getLogger(__name__)

# Escalation thresholds in overdue days (see docs/06-异常场景设计.md §6.1)
DUE_SOON_DAYS = 1      # advance warning: planned_end == today + 1
L1_DAYS = 1            # assignee
L2_DAYS = 2            # + project manager
L3_DAYS = 5            # + operations / admin
L4_DAYS = 10           # highest-level alert
ESCALATION_ROLES = ("operations", "admin")


async def _already_notified_today(
    db: AsyncSession, user_id: int, task_id: int, type: str = "overdue"
) -> bool:
    """Return True if a notification of `type` was already sent to this user for this task today."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.type == type,
                Notification.related_task_id == task_id,
                Notification.created_at >= today_start,
            )
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


def _overdue_message(task_title: str, overdue_days: int) -> tuple[str, str]:
    """Map overdue days to (title, content) for the highest applicable escalation band."""
    if overdue_days >= L4_DAYS:
        return (
            f"任务超期严重告警: {task_title}",
            f"任务已超期 {overdue_days} 天，请重新评估排期并决定是否暂停项目。",
        )
    if overdue_days >= L3_DAYS:
        return (
            f"任务严重超期: {task_title}",
            f"任务已超期 {overdue_days} 天，已升级至运营，请协调推进。",
        )
    if overdue_days >= L2_DAYS:
        return (
            f"任务超期升级: {task_title}",
            f"任务已超期 {overdue_days} 天，请负责人与项目经理推进处理。",
        )
    return (
        f"任务超期提醒: {task_title}",
        f"任务已超期 {overdue_days} 天，请尽快处理。",
    )


async def _run_checks(db: AsyncSession) -> int:
    """
    Scan tasks and emit escalation / advance-warning notifications.

    Overdue escalation (status active/review, planned_end < today), cumulative recipients:
      >= 1 day  → assignee
      >= 2 days → + project manager
      >= 5 days → + operations / admin
      >= 10 days → highest-level alert (same recipients, stronger message)
    Advance warning (status active, planned_end == today + 1) → assignee.

    Each recipient gets at most one notification of a given type per task per day.
    Only adds notifications to the session; the caller is responsible for committing.
    """
    today = date.today()
    notified = 0

    # operations / admin recipients for L3+ — fetched once
    esc_rows = await db.execute(
        select(User.id).where(
            User.role.in_(ESCALATION_ROLES),
            User.is_active == True,
        )
    )
    escalation_user_ids = [row[0] for row in esc_rows.all()]

    # --- Overdue escalation ---
    overdue_result = await db.execute(
        select(Task).where(
            Task.status.in_(["active", "review"]),
            Task.planned_end.is_not(None),
            Task.planned_end < today,
        )
    )
    for task in overdue_result.scalars().all():
        overdue_days = (today - task.planned_end).days

        # Build recipient set for the applicable band.
        recipients: set[int] = set()
        if task.assignee_id:
            recipients.add(task.assignee_id)
        if overdue_days >= L2_DAYS and task.project_id:
            project = await db.get(Project, task.project_id)
            if project and project.pm_id:
                recipients.add(project.pm_id)
        if overdue_days >= L3_DAYS:
            recipients.update(escalation_user_ids)

        title, content = _overdue_message(task.title, overdue_days)
        for user_id in recipients:
            if await _already_notified_today(db, user_id, task.id, "overdue"):
                continue
            await notify(
                db,
                user_id=user_id,
                type="overdue",
                title=title,
                content=content,
                related_task_id=task.id,
                related_project_id=task.project_id,
            )
            notified += 1

    # --- Advance warning (due tomorrow) ---
    due_soon_result = await db.execute(
        select(Task).where(
            Task.status == "active",
            Task.planned_end == today + timedelta(days=DUE_SOON_DAYS),
        )
    )
    for task in due_soon_result.scalars().all():
        if not task.assignee_id:
            continue
        if await _already_notified_today(db, task.assignee_id, task.id, "due_soon"):
            continue
        await notify(
            db,
            user_id=task.assignee_id,
            type="due_soon",
            title=f"任务即将到期: {task.title}",
            content="任务将于明天到期，请提前安排。",
            related_task_id=task.id,
            related_project_id=task.project_id,
        )
        notified += 1

    return notified


async def check_overdue_tasks() -> None:
    """Scheduler entry point: open a session, run checks, commit."""
    async with async_session() as db:
        notified = await _run_checks(db)
        if notified:
            await db.commit()
        logger.info(f"[scheduler] overdue check: {notified} notifications sent")
