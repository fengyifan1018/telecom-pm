from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User


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


async def notify_mentions(
    db: AsyncSession,
    content: str,
    sender_id: int,
    task_title: str,
    related_task_id: int | None = None,
    related_project_id: int | None = None,
):
    """解析评论中的 @提及（支持 @用户名 或 @显示名前缀，如 @李四 命中「李四(项目经理)」）并逐个通知。"""
    import re

    tokens = set(re.findall(r"@([^\s@]+)", content or ""))
    if not tokens:
        return
    users = (await db.execute(select(User))).scalars().all()
    mentioned = set()
    for u in users:
        short_name = u.display_name.split("(")[0].strip()
        for t in tokens:
            if t in (u.username, u.display_name, short_name) and u.id != sender_id:
                mentioned.add(u.id)
    for uid in mentioned:
        await notify(
            db,
            uid,
            "mention",
            "评论中提到了你",
            f"在任务「{task_title}」的评论中提到了你",
            related_task_id=related_task_id,
            related_project_id=related_project_id,
        )
