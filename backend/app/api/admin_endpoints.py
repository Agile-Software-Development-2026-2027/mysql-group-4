from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import current_superuser
from app.db.session import get_async_session
from app.db.models import User
from app.schemas.page import Page
from app.schemas.user import UserRead
from app.crud.user_crud import crud_user

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/users", response_model=Page[UserRead])
async def get_users(
    session: AsyncSession = Depends(get_async_session),
    admin: User = Depends(current_superuser),
    page: int = Query(default=0, ge=0),
    size: int = Query(default=20, ge=1, le=100),
    name: str | None = Query(default=None, min_length=1, pattern=r".*\S.*"),
):
    if name is not None:
        return await crud_user.get_users_by_name(session, name, page=page, size=size)
    return await crud_user.get_all_users(session=session, page=page, size=size)
