import asyncio
import uuid
from typing import Optional, Union
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, exceptions
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.core.config import settings
from app.db.models import User
from app.db.session import get_user_db
from app.schemas.user import UserCreate
from app.security.auth import auth_backend
from app.services.mail_service import send_email, send_password_reset_email


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY
    reset_password_token_lifetime_seconds = settings.RESET_PASSWORD_TOKEN_LIFETIME_SECONDS

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        asyncio.create_task(send_email(email=user.email, name=user.name))

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        await send_password_reset_email(name=user.name, email=user.email, token=token)

    async def validate_password(
        self, password: str, user: Union[UserCreate, User]
    ) -> None:
        if len(password) < 8:
            raise exceptions.InvalidPasswordException(reason="Password should be at least 8 characters")

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
