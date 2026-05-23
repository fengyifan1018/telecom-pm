from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.permissions import require_roles, require_permission
from app.models.user import User
from app.models.workflow_template import WorkflowTemplate
from app.schemas.template import TemplateResponse

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    product_type: str
    name: str
    phases: list[Any]


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    phases: Optional[list[Any]] = None


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("pm", "operations", "procurement", "network_engineer", "field_engineer", "admin")),
):
    query = select(WorkflowTemplate)
    if not include_inactive:
        query = query.where(WorkflowTemplate.is_active == True)
    result = await db.execute(query.order_by(WorkflowTemplate.id))
    return result.scalars().all()


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = await db.get(WorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("template.manage")),
):
    if not data.phases:
        raise HTTPException(status_code=400, detail="phases不能为空")
    template = WorkflowTemplate(
        product_type=data.product_type,
        name=data.name,
        phases=data.phases,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("template.manage")),
):
    template = await db.get(WorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    update_data = data.model_dump(exclude_none=True)
    if "phases" in update_data and not update_data["phases"]:
        raise HTTPException(status_code=400, detail="phases不能为空")
    # Bump version when phases change
    if "phases" in update_data:
        template.version += 1
    for field, value in update_data.items():
        setattr(template, field, value)
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("template.manage")),
):
    template = await db.get(WorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.is_active = False
    await db.commit()
