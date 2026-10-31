from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.db.session import create_db_and_tables
from app.api.user_endpoints import user_router
from app.api.admin_endpoints import admin_router
from app.api.mission_endpoints import mission_router
from app.security import fastapi_users, auth_backend
from app.schemas.user import UserRead, UserCreate
from app.core.exception_handler import register_exception_handlers
from app.api.location_endpoints import router as location_router
from app.api.document_endpoints import router as document_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(
    title="MySOL Backend",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    user_router,
    prefix="/api/v1",
)

app.include_router(
    admin_router,
    prefix="/api/v1",
)

app.include_router(
    mission_router,
    prefix="/api/v1",
)

app.include_router(
    location_router,
    prefix="/api/v1",
)

app.include_router(
    document_router, 
    prefix="/api/v1")