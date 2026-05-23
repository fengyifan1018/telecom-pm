from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    user_name: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50), index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(30), index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer)
    resource_name: Mapped[Optional[str]] = mapped_column(String(200))
    detail: Mapped[Optional[str]] = mapped_column(Text)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
