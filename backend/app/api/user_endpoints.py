from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_session
from app.db.models import User
from app.schemas.user import UserRead, UserUpdate
from app.security import current_active_user

user_router = APIRouter(tags=["users"])


@user_router.get("/")
async def greeting():
    return {"message": "Hello World"}


#Esempio endpoint protetto
@user_router.get("/me", response_model=UserRead)
async def get_current_user_profile(user: User = Depends(current_active_user)):
    return user


@user_router.patch("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
async def update_current_user_profile(
    payload: UserUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.surname is not None:
        user.surname = payload.surname.strip()
    if payload.department is not None:
        user.department = payload.department.strip()

    await session.commit()
    await session.refresh(user)
    return user

@user_router.get("/users/fund-managers", response_model=List[UserRead], status_code=status.HTTP_200_OK)
async def get_fund_managers(session: AsyncSession=Depends(get_async_session), user: User=Depends(current_active_user)):
    ########################################################################################################
    #DECOMMENTARE APPENA SARA CREATA L'ENTITA FUND
    #stmt=(select(User).join(Fund, Fund.responsible_fc==User.id).where(User.is_active==True).distinct())

    #TOGLIERE APPENA SARA CREATA L'ENTITA FUND
    stmt = select(User).where(User.is_active == True)
    ########################################################################################################
    result=await session.execute(stmt)
    return result.scalars().all()