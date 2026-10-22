from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import current_superuser
from app.db.session import get_async_session
from app.schemas.user import UserRead
from app.crud.user_crud import crud_user

admin_router = APIRouter(prefix="/admin", tags=["admin"])


#Esempio endpoint protetto per superuser
@admin_router.get("/users", response_model=list[UserRead])
async def get_users(session: AsyncSession = Depends(get_async_session), admin = Depends(current_superuser)):
    return await crud_user.get_all_users(session=session)

