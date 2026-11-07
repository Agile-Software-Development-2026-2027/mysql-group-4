from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.fund_repository import FundRepository
from app.crud.mission_repository import MissionRepository
from app.crud.user_repository import UserRepository
from app.db.session import get_async_session
from app.services.fund_service import FundService
from app.services.mission_service import MissionService

from app.crud.refund_repository import refund_repository
from app.services.refund_service import RefundService


def get_mission_service(
    session: AsyncSession = Depends(get_async_session),
) -> MissionService:
    repository = MissionRepository(session)
    user_repository = UserRepository()
    return MissionService(
        session=session,
        repository=repository,
        user_repository=user_repository,
    )


def get_fund_service(
    session: AsyncSession = Depends(get_async_session),
) -> FundService:
    return FundService(
        session=session,
        repository=FundRepository(session),
        user_repository=UserRepository(),
    )

def get_refund_service(session: AsyncSession = Depends(get_async_session)) -> RefundService:
    return RefundService(session=session, refund_repository = refund_repository, mission_repository = MissionRepository(session))