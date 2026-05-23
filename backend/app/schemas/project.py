from datetime import date, datetime
from typing import Optional

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

    model_config = {"from_attributes": True}
