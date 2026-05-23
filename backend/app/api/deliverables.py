import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_current_user
from app.models.phase_deliverable import PhaseDeliverable
from app.models.project import Project
from app.models.user import User

router = APIRouter(prefix="/api/projects/{project_id}/deliverables", tags=["deliverables"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _d_dict(d: PhaseDeliverable, uploader_name: str | None = None) -> dict:
    return {
        "id": d.id,
        "project_id": d.project_id,
        "phase": d.phase,
        "title": d.title,
        "original_name": d.original_name,
        "size": d.size,
        "content_type": d.content_type,
        "uploaded_by": d.uploaded_by,
        "uploader_name": uploader_name,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.post("", status_code=201)
async def upload_deliverable(
    project_id: int,
    phase: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件大小不能超过50MB")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.UPLOAD_DIR, stored_name), "wb") as f:
        f.write(content)

    deliverable = PhaseDeliverable(
        project_id=project_id,
        phase=phase,
        title=title,
        filename=stored_name,
        original_name=file.filename or "unknown",
        content_type=file.content_type,
        size=len(content),
        uploaded_by=current_user.id,
    )
    db.add(deliverable)
    await db.commit()
    await db.refresh(deliverable)
    return _d_dict(deliverable)


@router.get("")
async def list_deliverables(
    project_id: int,
    phase: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = (
        select(PhaseDeliverable, User.display_name.label("uploader_name"))
        .join(User, PhaseDeliverable.uploaded_by == User.id)
        .where(PhaseDeliverable.project_id == project_id)
        .order_by(PhaseDeliverable.created_at.desc())
    )
    if phase:
        query = query.where(PhaseDeliverable.phase == phase)

    result = await db.execute(query)
    return [_d_dict(d, uploader_name) for d, uploader_name in result.all()]


@router.get("/{deliverable_id}/download")
async def download_deliverable(
    project_id: int,
    deliverable_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = await db.get(PhaseDeliverable, deliverable_id)
    if not d or d.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    file_path = os.path.join(settings.UPLOAD_DIR, d.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(file_path, filename=d.original_name, media_type=d.content_type or "application/octet-stream")


@router.delete("/{deliverable_id}", status_code=204)
async def delete_deliverable(
    project_id: int,
    deliverable_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = await db.get(PhaseDeliverable, deliverable_id)
    if not d or d.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    if d.uploaded_by != current_user.id and current_user.role not in ("pm", "admin"):
        raise HTTPException(status_code=403, detail="只有上传者或PM/管理员可以删除")
    file_path = os.path.join(settings.UPLOAD_DIR, d.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    await db.delete(d)
    await db.commit()
