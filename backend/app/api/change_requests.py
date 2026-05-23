from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.permissions import require_roles, require_permission
from app.models.change_request import ChangeRequest
from app.models.project import Project
from app.models.user import User
from app.services.notification_service import notify

router = APIRouter(prefix="/api/projects", tags=["change-requests"])


class CRCreate(BaseModel):
    title: str
    reason: str
    description: Optional[str] = None


class CRReject(BaseModel):
    reject_reason: str


async def _next_cr_no(db: AsyncSession) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    result = await db.execute(
        select(ChangeRequest)
        .where(ChangeRequest.cr_no.like(f"CR-{today}-%"))
        .order_by(ChangeRequest.id.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    seq = 1
    if last:
        seq = int(last.cr_no.split("-")[-1]) + 1
    return f"CR-{today}-{seq:04d}"


@router.post("/{project_id}/change-requests", status_code=201)
async def create_change_request(
    project_id: int,
    data: CRCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("cr.create")),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    cr = ChangeRequest(
        cr_no=await _next_cr_no(db),
        project_id=project_id,
        title=data.title,
        reason=data.reason,
        description=data.description,
        requested_by=current_user.id,
    )
    db.add(cr)
    await db.flush()

    if project.pm_id and project.pm_id != current_user.id:
        await notify(
            db, project.pm_id, "cr_submitted",
            f"变更申请待审批: {cr.title}",
            content=cr.reason[:100],
            related_project_id=project_id,
        )

    await db.commit()
    await db.refresh(cr)
    return _cr_dict(cr)


@router.get("/{project_id}/change-requests")
async def list_change_requests(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChangeRequest, User.display_name.label("requester_name"))
        .join(User, ChangeRequest.requested_by == User.id)
        .where(ChangeRequest.project_id == project_id)
        .order_by(ChangeRequest.id.desc())
    )
    return [_cr_dict(cr, requester_name) for cr, requester_name in result.all()]


@router.put("/{project_id}/change-requests/{cr_id}/approve")
async def approve_change_request(
    project_id: int,
    cr_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("cr.approve")),
):
    cr = await db.get(ChangeRequest, cr_id)
    if not cr or cr.project_id != project_id:
        raise HTTPException(status_code=404, detail="Change request not found")
    if cr.status != "pending":
        raise HTTPException(status_code=400, detail="只能审批待审状态的变更申请")

    cr.status = "approved"
    cr.approved_by = current_user.id
    cr.approved_at = datetime.utcnow()

    await notify(
        db, cr.requested_by, "cr_approved",
        f"变更申请已批准: {cr.title}",
        related_project_id=project_id,
    )
    await db.commit()
    await db.refresh(cr)
    return _cr_dict(cr)


@router.put("/{project_id}/change-requests/{cr_id}/reject")
async def reject_change_request(
    project_id: int,
    cr_id: int,
    data: CRReject,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("cr.approve")),
):
    cr = await db.get(ChangeRequest, cr_id)
    if not cr or cr.project_id != project_id:
        raise HTTPException(status_code=404, detail="Change request not found")
    if cr.status != "pending":
        raise HTTPException(status_code=400, detail="只能审批待审状态的变更申请")

    cr.status = "rejected"
    cr.approved_by = current_user.id
    cr.approved_at = datetime.utcnow()
    cr.reject_reason = data.reject_reason

    await notify(
        db, cr.requested_by, "cr_rejected",
        f"变更申请已拒绝: {cr.title}",
        content=data.reject_reason[:100],
        related_project_id=project_id,
    )
    await db.commit()
    await db.refresh(cr)
    return _cr_dict(cr)


def _cr_dict(cr: ChangeRequest, requester_name: str | None = None) -> dict:
    return {
        "id": cr.id,
        "cr_no": cr.cr_no,
        "project_id": cr.project_id,
        "title": cr.title,
        "reason": cr.reason,
        "description": cr.description,
        "status": cr.status,
        "requested_by": cr.requested_by,
        "requester_name": requester_name,
        "approved_by": cr.approved_by,
        "reject_reason": cr.reject_reason,
        "created_at": cr.created_at,
        "approved_at": cr.approved_at,
    }
