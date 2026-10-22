from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserCRUD:
    async def get_all_users(self, session: AsyncSession) -> Sequence[User]:
        query = select(User)
        users = await session.execute(query)
        return users.scalars().all()


crud_user = UserCRUD()