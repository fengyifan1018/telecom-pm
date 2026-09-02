from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    id: int
    project_id: int
    parent_task_id: Optional[int]
    task_no: str
    title: str
    description: Optional[str]
    phase: str
    status: str
    is_required: bool
    assignee_id: Optional[int]
    reviewer_id: Optional[int]
    priority: int
    planned_start: Optional[date]
    planned_end: Optional[date]
    actual_start: Optional[date]
    actual_end: Optional[date]
    estimated_days: int
    rework_count: int
    progress: int = 0
    auto_schedule: bool = True
    created_at: datetime
    # 仅 PUT 更新排期时回传：本次联动顺延的后续任务数
    rescheduled: Optional[int] = None

    model_config = {"from_attributes": True}


class TaskUpdate(BaseModel):
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None
    priority: Optional[int] = None
    description: Optional[str] = None
    auto_schedule: Optional[bool] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100)


class TaskAssign(BaseModel):
    assignee_id: int
    reviewer_id: Optional[int] = None


class RelationCreate(BaseModel):
    relation_type: Literal["precedes", "blocks"]
    related_task_id: int
    # in：related 指向当前任务（related 是我的前置/阻塞我的任务）；out：当前任务指向 related
    direction: Literal["in", "out"] = "in"


class TaskAction(BaseModel):
    remark: Optional[str] = None


class TaskTransitionResponse(BaseModel):
    id: int
    task_id: int
    from_status: Optional[str]
    to_status: str
    operator_id: int
    remark: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
