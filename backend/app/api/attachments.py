import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_current_user
from app.models.attachment import Attachment
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/api/tasks/{task_id}/attachments", tags=["attachments"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("", status_code=201)
async def upload_attachment(
    task_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件大小不能超过20MB")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, stored_name)

    with open(file_path, "wb") as f:
        f.write(content)

    attachment = Attachment(
        task_id=task_id,
        filename=stored_name,
        original_name=file.filename or "unknown",
        content_type=file.content_type,
        size=len(content),
        uploader_id=current_user.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return {
        "id": attachment.id,
        "original_name": attachment.original_name,
        "size": attachment.size,
        "content_type": attachment.content_type,
        "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
        "uploader_id": attachment.uploader_id,
    }


@router.get("")
async def list_attachments(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    result = await db.execute(
        select(Attachment).where(Attachment.task_id == task_id).order_by(Attachment.created_at.desc())
    )
    attachments = result.scalars().all()
    return [
        {
            "id": a.id,
            "original_name": a.original_name,
            "size": a.size,
            "content_type": a.content_type,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "uploader_id": a.uploader_id,
        }
        for a in attachments
    ]


@router.get("/{attachment_id}/download")
async def download_attachment(
    task_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment = await db.get(Attachment, attachment_id)
    if not attachment or attachment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    file_path = os.path.join(settings.UPLOAD_DIR, attachment.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        file_path,
        filename=attachment.original_name,
        media_type=attachment.content_type or "application/octet-stream",
    )


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    task_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment = await db.get(Attachment, attachment_id)
    if not attachment or attachment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if attachment.uploader_id != current_user.id and current_user.role not in ("pm", "admin"):
        raise HTTPException(status_code=403, detail="只有上传者或管理员可以删除附件")
    file_path = os.path.join(settings.UPLOAD_DIR, attachment.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    await db.delete(attachment)
    await db.commit()
