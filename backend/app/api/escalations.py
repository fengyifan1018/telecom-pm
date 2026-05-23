from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.escalation import TaskEscalation
from app.models.task import Task
from app.models.user import User
from app.services.notification_service import notify

router = APIRouter(prefix="/api/tasks/{task_id}/escalations", tags=["escalations"])


class EscalationCreate(BaseModel):
    severity: str = "medium"
    description: str


class EscalationResolve(BaseModel):
    resolution: str


@router.post("", status_code=201)
async def create_escalation(
    task_id: int,
    data: EscalationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    escalation = TaskEscalation(
        task_id=task_id,
        raised_by=current_user.id,
        severity=data.severity,
        description=data.description,
    )
    db.add(escalation)

    if task.reviewer_id:
        await notify(db, task.reviewer_id, "escalation", f"任务问题升级: {task.title}", content=data.description, related_task_id=task.id, related_project_id=task.project_id)

    await db.commit()
    await db.refresh(escalation)
    return {
        "id": escalation.id,
        "task_id": escalation.task_id,
        "severity": escalation.severity,
        "status": escalation.status,
        "description": escalation.description,
        "raised_by": escalation.raised_by,
        "created_at": escalation.created_at.isoformat() if escalation.created_at else None,
    }


@router.get("")
async def list_escalations(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    result = await db.execute(
        select(TaskEscalation).where(TaskEscalation.task_id == task_id).order_by(TaskEscalation.created_at.desc())
    )
    items = result.scalars().all()
    return [
        {
            "id": e.id,
            "severity": e.severity,
            "status": e.status,
            "description": e.description,
            "resolution": e.resolution,
            "raised_by": e.raised_by,
            "resolved_by": e.resolved_by,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        }
        for e in items
    ]


@router.put("/{escalation_id}/resolve")
async def resolve_escalation(
    task_id: int,
    escalation_id: int,
    data: EscalationResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    escalation = await db.get(TaskEscalation, escalation_id)
    if not escalation or escalation.task_id != task_id:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if escalation.status == "resolved":
        raise HTTPException(status_code=400, detail="已解决")

    escalation.status = "resolved"
    escalation.resolution = data.resolution
    escalation.resolved_by = current_user.id
    escalation.resolved_at = datetime.utcnow()

    task = await db.get(Task, task_id)
    if task and escalation.raised_by != current_user.id:
        await notify(db, escalation.raised_by, "escalation", f"问题已解决: {task.title}", content=data.resolution, related_task_id=task.id, related_project_id=task.project_id)

    await db.commit()
    return {"detail": "已解决"}
