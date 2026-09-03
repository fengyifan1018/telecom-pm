from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, DateTime, Date, Integer, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.timeutil import now_cn


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    parent_task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"))
    task_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/active/review/done/paused/blocked/rework/cancelled
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    priority: Mapped[int] = mapped_column(Integer, default=3)
    planned_start: Mapped[Optional[date]] = mapped_column(Date)
    planned_end: Mapped[Optional[date]] = mapped_column(Date)
    actual_start: Mapped[Optional[date]] = mapped_column(Date)
    actual_end: Mapped[Optional[date]] = mapped_column(Date)
    estimated_days: Mapped[int] = mapped_column(Integer, default=1)
    rework_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    # 完成进度 0-100；approve 置 100，长周期任务可连续报量
    progress: Mapped[int] = mapped_column(Integer, default=0)
    # 排期联动开关：True 时前置任务（precedes）改期会自动顺延本任务
    auto_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn, onupdate=now_cn)


class TaskRelation(Base):
    """任务间业务关系：precedes（前置，日期联动的依据）/ blocks（阻塞，流转卡点）。

    from → to 语义：from_task 在前（precedes）或 from_task 阻塞 to_task（blocks）。
    """
    __tablename__ = "task_relations"
    __table_args__ = (UniqueConstraint("from_task_id", "to_task_id", "relation_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    from_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    to_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(20))  # precedes / blocks
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)


class TaskTransition(Base):
    __tablename__ = "task_transitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)


class TaskWatcher(Base):
    """任务关注：非参与者订阅任务动态，状态变更时收到通知。"""
    __tablename__ = "task_watchers"
    __table_args__ = (UniqueConstraint("task_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_cn)
