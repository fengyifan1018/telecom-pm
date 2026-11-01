from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.timeutil import now_cn


class WecomBindRequest(Base):
    """成员给机器人发消息产生的企微账号绑定记录。

    bound_user_id 为空 = 待管理员指认的候选；非空 = 已绑定。
    wecom_userid 唯一（一个企微账号一条记录）；bound_user_id 唯一（一个系统用户一个绑定）。
    """
    __tablename__ = "wecom_bind_requests"
    __table_args__ = (
        UniqueConstraint("wecom_userid"),
        UniqueConstraint("bound_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wecom_userid: Mapped[str] = mapped_column(String(64), index=True)
    last_content: Mapped[str | None] = mapped_column(Text)
    bound_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    last_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)
