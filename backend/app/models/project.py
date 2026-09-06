from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DateTime, Date, Numeric, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.timeutil import now_cn


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(50))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    product_type: Mapped[str] = mapped_column(String(20))  # dia/transmission/dark_fiber/sdwan
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/active/suspended/completed/cancelled
    priority: Mapped[int] = mapped_column(Integer, default=3)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    pm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    contract_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    planned_start: Mapped[Optional[date]] = mapped_column(Date)
    planned_end: Mapped[Optional[date]] = mapped_column(Date)
    actual_start: Mapped[Optional[date]] = mapped_column(Date)
    actual_end: Mapped[Optional[date]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn, onupdate=now_cn)
    # 立项审核：提交人 / 最近驳回原因
    init_submitted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    init_reject_reason: Mapped[Optional[str]] = mapped_column(Text)
