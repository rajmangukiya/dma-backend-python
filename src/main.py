from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import src.database.models  # noqa: F401  (registers every table, so cross-module references resolve)
from src.common.config import get_settings
from src.common.errors import register_error_handlers
from src.database.session import engine
from src.router import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()  # close pooled database connections


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Same as the Node API: the React app (and its cookies) may call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.client_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(api_router, prefix="/api")
