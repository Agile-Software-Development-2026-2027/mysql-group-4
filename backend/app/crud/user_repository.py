from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.pagination import paginate
from app.db.models import User
from app.schemas.page import Page


class UserRepository:
    async def get_all_users(
        self, session: AsyncSession, *, page: int = 0, size: int = 20
    ) -> Page[User]:
        query = select(User).order_by(User.name, User.surname, User.id)
        return await paginate(session, query, page, size)

    async def get_user_by_id(self, session: AsyncSession, user_id: UUID) -> User | None:
        return await session.get(User, user_id)

    async def get_users_by_name(
        self, session: AsyncSession, name: str, *, page: int = 0, size: int = 20
    ) -> Page[User]:
        name = name.strip()
        if not name:
            raise ValueError("User name cannot be empty")
        query = (
            select(User)
            .where(User.name.icontains(name, autoescape=True))
            .order_by(User.name, User.surname, User.id)
        )
        return await paginate(session, query, page, size)


user_repository = UserRepository()
