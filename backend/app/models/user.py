from datetime import datetime

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.timeutil import now_cn


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20))  # sales/pm/operations/procurement/network_engineer/field_engineer/admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)
