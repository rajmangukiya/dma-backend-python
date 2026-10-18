from fastapi import APIRouter

from app.api.routes import health

# Every feature router is included here; main.py mounts this under /api
api_router = APIRouter()
api_router.include_router(health.router)
