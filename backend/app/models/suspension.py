from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, DateTime, Date, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProjectSuspension(Base):
    __tablename__ = "project_suspensions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    reason_category: Mapped[str] = mapped_column(String(30))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    suspended_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    suspended_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expected_resume: Mapped[Optional[date]] = mapped_column(Date)
    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resumed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    resume_note: Mapped[Optional[str]] = mapped_column(Text)
