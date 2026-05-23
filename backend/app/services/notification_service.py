from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def notify(
    db: AsyncSession,
    user_id: int,
    type: str,
    title: str,
    content: str | None = None,
    related_task_id: int | None = None,
    related_project_id: int | None = None,
):
    n = Notification(
        user_id=user_id,
        type=type,
        title=title,
        content=content,
        related_task_id=related_task_id,
        related_project_id=related_project_id,
    )
    db.add(n)
