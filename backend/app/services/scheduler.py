"""Background scheduler: runs overdue task checks periodically."""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.task import Task
from app.models.project import Project
from app.models.notification import Notification
from app.services.notification_service import notify

logger = logging.getLogger(__name__)


async def _already_notified_today(db: AsyncSession, user_id: int, task_id: int) -> bool:
    """Return True if an overdue notification was already sent to this user for this task today."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.type == "overdue",
                Notification.related_task_id == task_id,
                Notification.created_at >= today_start,
            )
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def check_overdue_tasks() -> None:
    """
    Scan all active/review tasks past their planned_end.
    - Overdue >= 1 day  → notify assignee (once per day)
    - Overdue >= 3 days → also notify PM (once per day)
    """
    today = date.today()
    async with async_session() as db:
        result = await db.execute(
            select(Task).where(
                Task.status.in_(["active", "review"]),
                Task.planned_end < today,
                Task.planned_end.is_not(None),
            )
        )
        tasks = result.scalars().all()

        notified = 0
        for task in tasks:
            overdue_days = (today - task.planned_end).days

            # Notify assignee (once per day)
            if task.assignee_id and not await _already_notified_today(db, task.assignee_id, task.id):
                await notify(
                    db,
                    user_id=task.assignee_id,
                    type="overdue",
                    title=f"任务超期提醒: {task.title}",
                    content=f"任务已超期 {overdue_days} 天，请尽快处理。",
                    related_task_id=task.id,
                    related_project_id=task.project_id,
                )
                notified += 1

            # Also notify PM when overdue >= 3 days
            if overdue_days >= 3 and task.project_id:
                project = await db.get(Project, task.project_id)
                if project and project.pm_id and project.pm_id != task.assignee_id:
                    if not await _already_notified_today(db, project.pm_id, task.id):
                        await notify(
                            db,
                            user_id=project.pm_id,
                            type="overdue",
                            title=f"任务严重超期: {task.title}",
                            content=f"任务已超期 {overdue_days} 天，请关注并推进处理。",
                            related_task_id=task.id,
                            related_project_id=task.project_id,
                        )
                        notified += 1

        if tasks:
            await db.commit()

        logger.info(f"[scheduler] overdue check: {len(tasks)} overdue tasks, {notified} notifications sent")
