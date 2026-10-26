from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.mission_repository import MissionRepository
from app.crud.user_repository import UserRepository
from app.db.session import get_async_session
from app.services.mission_service import MissionService
from app.validators.mission_validator import MissionValidator
from app.validators.user_validator import UserValidator


def get_mission_service(
    session: AsyncSession = Depends(get_async_session),
) -> MissionService:
    repository = MissionRepository(session)
    return MissionService(
        session=session,
        repository=repository,
        mission_validator=MissionValidator(repository),
        user_validator=UserValidator(UserRepository(), session),
    )
