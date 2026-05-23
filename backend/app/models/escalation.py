from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskEscalation(Base):
    __tablename__ = "task_escalations"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    raised_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    severity: Mapped[str] = mapped_column(String(20), default="medium")  # low/medium/high/critical
    status: Mapped[str] = mapped_column(String(20), default="open")  # open/in_progress/resolved
    description: Mapped[str] = mapped_column(Text)
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    resolved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
