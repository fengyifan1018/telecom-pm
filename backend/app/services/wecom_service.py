"""企业微信智能机器人推送（官方 wecom-aibot-python-sdk 长连接）。

outbox 模式：站内通知产生时 push_status=pending；wecom_client 长连接进程
周期扫描 pending（含 ≤3 次重试的 failed）通知，经长连接按单聊推送给收件人。
收件人映射：users.wecom_userid（企微通讯录 userid），未配置则标记 skipped。
"""
import os

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User

MAX_ATTEMPTS = 3
PER_CHAT_LIMIT = 25  # 企微限频 30 条/分/会话，留余量

WECHAT_BOT_ID = os.getenv("WECHAT_BOT_ID", "")
WECHAT_BOT_SECRET = os.getenv("WECHAT_BOT_SECRET", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "")


def format_content(n: Notification) -> str:
    """通知 → 企微 markdown 正文。"""
    lines = [f"**{n.title}**"]
    if n.content:
        lines.append(n.content)
    if n.related_project_id:
        url = f"{APP_BASE_URL}/projects/{n.related_project_id}" if APP_BASE_URL else None
        if url:
            lines.append(f"[点击查看]({url})")
    lines.append(f"> {n.created_at:%m-%d %H:%M} · 通信项目管理系统")
    return chr(10).join(lines)


async def push_pending(db: AsyncSession, sender=None, limit: int = 50) -> int:
    """扫描待推通知并经智能机器人单聊推送。sender 可注入用于测试。返回推送条数。

    sender: async (chatid, body) -> None  （生产为长连接客户端的 send_message）
    """
    if sender is None:
        if not WECHAT_BOT_ID:
            return 0  # 未配置智能机器人 → 推送关闭
        from app.wecom_client import get_client
        client = get_client()
        if client is None or not client.connected:
            return 0
        sender = client.send_message

    rows = await db.execute(
        select(Notification, User.wecom_userid)
        .join(User, User.id == Notification.user_id)
        .where(
            or_(
                Notification.push_status == "pending",
                and_(Notification.push_status == "failed", Notification.push_attempts < MAX_ATTEMPTS),
            )
        )
        .order_by(Notification.id)
        .limit(limit)
    )
    sent = 0
    per_chat: dict[str, int] = {}
    for n, wxid in rows.all():
        if not wxid:
            n.push_status = "skipped"
            n.push_error = "收件人未配置企微账号"
            continue
        if per_chat.get(wxid, 0) >= PER_CHAT_LIMIT:
            continue  # 超本轮会话限频，留待下轮
        body = {"msgtype": "markdown", "markdown": {"content": format_content(n)}}
        try:
            await sender(wxid, body)
            n.push_status = "sent"
            n.push_error = None
            sent += 1
        except Exception as e:  # noqa: BLE001 记录错误待重试
            n.push_status = "failed"
            n.push_attempts += 1
            n.push_error = str(e)[:250]
        per_chat[wxid] = per_chat.get(wxid, 0) + 1
    await db.commit()
    return sent
