from fastapi import APIRouter

from src.admin.views import router as admin_router
from src.auth.views import router as auth_router
from src.document_skeletons.views import router as skeletons_router
from src.documents.views import router as documents_router
from src.health.views import router as health_router
from src.journeys.views import router as journeys_router
from src.journeys.views import segments_router
from src.users.views import router as users_router

# Every module's router is included here; main.py mounts this under /api
api_router = APIRouter()
for router in (
    health_router,
    auth_router,
    admin_router,
    users_router,
    skeletons_router,
    journeys_router,
    segments_router,
    documents_router,
):
    api_router.include_router(router)
