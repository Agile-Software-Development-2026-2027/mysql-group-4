from fastapi import APIRouter, Depends

from app.security import current_active_user
from app.db.models import User
from app.schemas.user import UserRead

user_router = APIRouter(tags=["users"])


@user_router.get("/")
async def greeting():
    return {"message": "Hello World"}


#Esempio endpoint protetto
@user_router.get("/me", response_model=UserRead)
async def get_current_user_profile(user: User = Depends(current_active_user)):
    return user