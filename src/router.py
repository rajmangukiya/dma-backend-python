from fastapi import APIRouter

from src.auth.views import router as auth_router
from src.health.views import router as health_router

# Every module's router is included here; main.py mounts this under /api
api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
