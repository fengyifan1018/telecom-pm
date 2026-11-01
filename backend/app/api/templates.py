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


def _validate_phases(phases: list) -> None:
    """模板阶段结构校验：key 唯一、引用存在、无循环依赖、任务完整。"""
    if not phases:
        raise HTTPException(status_code=400, detail="phases不能为空")
    keys = set()
    for i, p in enumerate(phases):
        if not (p.get("phase") or "").strip():
            raise HTTPException(status_code=400, detail=f"第{i + 1}个阶段缺少 phase 标识")
        if not (p.get("name") or "").strip():
            raise HTTPException(status_code=400, detail=f"阶段 {p['phase']} 缺少名称")
        if p["phase"] in keys:
            raise HTTPException(status_code=400, detail=f"阶段标识 \"{p['phase']}\" 重复")
        keys.add(p["phase"])
        for j, t in enumerate(p.get("tasks") or []):
            if not (t.get("title") or "").strip():
                raise HTTPException(status_code=400, detail=f"阶段 \"{p['name']}\" 第{j + 1}个任务标题不能为空")
            if (t.get("estimated_days") or 0) < 1:
                raise HTTPException(status_code=400, detail=f"阶段 \"{p['name']}\" 第{j + 1}个任务预估天数需≥1")
    # depends_on 引用合法性
    for p in phases:
        for dep in p.get("depends_on") or []:
            if dep not in keys:
                raise HTTPException(status_code=400, detail=f"阶段 \"{p['phase']}\" 的前置 \"{dep}\" 不存在")
    # 环检测（DFS 染色）
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in keys}
    def dfs(k):
        color[k] = GRAY
        for p in phases:
            if p["phase"] == k:
                for dep in p.get("depends_on") or []:
                    if color.get(dep) == GRAY:
                        raise HTTPException(status_code=400, detail=f"前置阶段存在循环依赖：{k} → {dep}")
                    if color.get(dep) == WHITE:
                        dfs(dep)
        color[k] = BLACK
    for k in keys:
        if color[k] == WHITE:
            dfs(k)


async def _deactivate_others(db: AsyncSession, product_type: str, keep_id: int) -> None:
    """同一产品线仅保留一个启用模板：自动停用其他（切换生效语义）。"""
    result = await db.execute(
        select(WorkflowTemplate).where(
            WorkflowTemplate.product_type == product_type,
            WorkflowTemplate.is_active == True,
            WorkflowTemplate.id != keep_id,
        )
    )
    for tpl in result.scalars().all():
        tpl.is_active = False


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
    _validate_phases(data.phases)
    template = WorkflowTemplate(
        product_type=data.product_type,
        name=data.name,
        phases=data.phases,
    )
    db.add(template)
    await db.flush()
    await _deactivate_others(db, data.product_type, template.id)
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
    if "phases" in update_data:
        _validate_phases(update_data["phases"])
        template.version += 1
    for field, value in update_data.items():
        setattr(template, field, value)
    # 同产品线唯一启用：本次置为启用的自动停用其他
    if update_data.get("is_active"):
        await _deactivate_others(db, template.product_type, template.id)
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
