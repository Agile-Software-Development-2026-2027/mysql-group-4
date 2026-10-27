from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccessDeniedError, UserNotFoundError
from app.crud.user_repository import UserRepository
from app.db.models import User


class UserValidator:
    def __init__(self, repository: UserRepository, session: AsyncSession):
        self._repository = repository
        self._session = session

    async def get_user_or_throw(self, user_id: UUID) -> User:
        user = await self._repository.get_user_by_id(self._session, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    async def get_active_user_or_throw(self, user_id: UUID) -> User:
        user = await self.get_user_or_throw(user_id)
        if not user.is_active:
            raise AccessDeniedError(f"User {user_id} is inactive")
        return user
