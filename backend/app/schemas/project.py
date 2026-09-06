from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel


class CustomerCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class CustomerResponse(BaseModel):
    id: int
    name: str
    contact_name: Optional[str]
    contact_phone: Optional[str]
    created_at: Optional[datetime] = None
    project_count: Optional[int] = None

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str
    customer_id: int
    product_type: str
    priority: int = 3
    pm_id: Optional[int] = None
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    pm_id: Optional[int] = None
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    project_no: str
    name: str
    customer_id: int
    customer_name: Optional[str] = None
    product_type: str
    status: str
    priority: int
    sales_id: int
    sales_name: Optional[str] = None
    pm_id: Optional[int]
    pm_name: Optional[str] = None
    planned_start: Optional[date]
    planned_end: Optional[date]
    actual_start: Optional[date]
    actual_end: Optional[date]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    init_submitted_by: Optional[int] = None
    init_reject_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class InitApprovalRequest(BaseModel):
    action: Literal["approve", "reject"]
    reason: Optional[str] = None


class ProjectHealthResponse(ProjectResponse):
    """项目列表行 + 健康度聚合（完成度/超期/升级/延期/风险/验收）。"""
    task_total: int = 0
    task_done: int = 0
    progress_pct: int = 0
    overdue_count: int = 0
    open_escalations: int = 0
    is_delayed: bool = False
    at_risk: bool = False
    in_acceptance: bool = False
