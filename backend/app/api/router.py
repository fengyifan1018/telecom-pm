from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.tasks import router as tasks_router
from app.api.templates import router as templates_router
from app.api.dashboard import router as dashboard_router
from app.api.users import router as users_router
from app.api.notifications import router as notifications_router
from app.api.attachments import router as attachments_router
from app.api.escalations import router as escalations_router
from app.api.change_requests import router as change_requests_router
from app.api.deliverables import router as deliverables_router
from app.api.groups import router as groups_router
from app.api.permissions import router as permissions_router
from app.api.audit import router as audit_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(tasks_router)
api_router.include_router(templates_router)
api_router.include_router(dashboard_router)
api_router.include_router(users_router)
api_router.include_router(notifications_router)
api_router.include_router(attachments_router)
api_router.include_router(escalations_router)
api_router.include_router(change_requests_router)
api_router.include_router(deliverables_router)
api_router.include_router(groups_router)
api_router.include_router(permissions_router)
api_router.include_router(audit_router)
