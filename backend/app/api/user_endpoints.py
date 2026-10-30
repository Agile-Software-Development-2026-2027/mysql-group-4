from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_session
from app.db.models import User
from app.schemas.user import UserRead
from app.security import current_active_user

user_router = APIRouter(tags=["users"])


@user_router.get("/")
async def greeting():
    return {"message": "Hello World"}


#Esempio endpoint protetto
@user_router.get("/me", response_model=UserRead)
async def get_current_user_profile(user: User = Depends(current_active_user)):
    return user

@user_router.get("/fund-managers", response_model=List[UserRead], status_code=status.HTTP_200_OK)
async def get_fund_managers(session: AsyncSession=Depends(get_async_session)):
    result=await session.execute(select(User).where(User.is_active==True))
    return result.scalars().all()