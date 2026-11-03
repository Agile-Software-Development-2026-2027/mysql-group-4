import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccessDeniedError,
    FundLockedError,
    FundNotFoundError,
    UserNotFoundError,
)
from app.crud.fund_repository import FundRepository
from app.crud.user_repository import UserRepository
from app.db.fund import Fund
from app.db.models import User
from app.db.mission import Mission
from app.schemas.fund import FundCreateDTO, FundDTO, FundUpdateDTO
from app.schemas.page import Page, PageRequest

logger = logging.getLogger(__name__)


class FundService:
    def __init__(
        self,
        session: AsyncSession,
        repository: FundRepository,
        user_repository: UserRepository | None = None,
    ):
        self._session = session
        self._repository = repository
        self._user_repository = user_repository or UserRepository()

    async def get_fund_by_id(self, fund_id: UUID, user_id: UUID) -> FundDTO:
        user = await self._get_active_user_or_throw(user_id)
        fund = await self._get_fund_or_throw(fund_id)
        self._validate_user_can_read(fund, user)
        return (await self._to_dtos([fund]))[0]

    async def get_fund_by_mission_id(self, mission_id: UUID, user_id: UUID) -> FundDTO | None:
        user = await self._get_active_user_or_throw(user_id)
        stmt = select(Fund).where(Fund.locked_by_mission_id == mission_id)
        result = await self._session.execute(stmt)
        fund = result.scalars().first()
        if fund is None:
            return None

        if user.is_superuser or fund.responsible_fc == user.fiscal_code:
            return FundDTO.model_validate(fund)

        mission_stmt = select(Mission).where(Mission.id == mission_id)
        mission_res = await self._session.execute(mission_stmt)
        mission = mission_res.scalars().first()

        if mission and (user.is_superuser or mission.requester_id == user.id or mission.fund_manager_id == user.id):
            return FundDTO.model_validate(fund)

        raise AccessDeniedError("User cannot access this fund")

    async def get_funds(
        self, user_id: UUID, page_request: PageRequest | None = None
    ) -> Page[FundDTO]:
        user = await self._get_active_user_or_throw(user_id)
        visible_to = None if user.is_superuser else user.fiscal_code
        funds = await self._repository.find_all(
            responsible_fc=visible_to, page_request=page_request
        )
        return Page(
            content=await self._to_dtos(funds.content),
            total_elements=funds.total_elements,
            number=funds.number,
            size=funds.size,
        )

    async def get_available_funds(
        self, user_id: UUID, page_request: PageRequest | None = None
    ) -> Page[FundDTO]:
        await self._get_active_user_or_throw(user_id)
        funds = await self._repository.find_all(available_only=True, page_request=page_request)
        return funds.map(FundDTO.model_validate)

    async def create_fund(self, data: FundCreateDTO, user_id: UUID) -> FundDTO:
        async with self._transaction():
            user = await self._get_active_user_or_throw(user_id)
            fund = Fund(**data.model_dump())
            fund.responsible_fc = user.fiscal_code
            fund.responsible = user
            fund.created_by = user.id
            fund.updated_by = user.id
            saved = await self._repository.save(fund)
            result = FundDTO.model_validate(saved)
        logger.info("Fund %s created by user %s", result.id, user_id)
        return result

    async def update_fund(
        self, fund_id: UUID, data: FundUpdateDTO, user_id: UUID
    ) -> FundDTO:
        async with self._transaction():
            user = await self._get_active_user_or_throw(user_id)
            fund = await self._get_fund_or_throw(fund_id, for_update=True)
            self._validate_user_is_responsible(fund, user)
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(fund, field, value)
            fund.updated_by = user.id
            saved = await self._repository.save(fund)
            result = FundDTO.model_validate(saved)
        logger.info("Fund %s updated by user %s", fund_id, user_id)
        return result

    async def delete_fund(self, fund_id: UUID, user_id: UUID, *, force: bool = False) -> None:
        async with self._transaction():
            user = await self._get_active_user_or_throw(user_id)
            fund = await self._get_fund_or_throw(fund_id, for_update=True)
            self._validate_user_is_responsible(fund, user)
            if fund.locked_by_mission_id is not None and not force:
                raise FundLockedError(fund.id)
            await self._repository.delete(fund)
        logger.info("Fund %s deleted by user %s", fund_id, user_id)

    async def lock_for_mission(
        self, fund_id: UUID, mission_id: UUID, *, responsible_fc: str | None = None
    ) -> Fund:
        fund = await self._get_fund_or_throw(fund_id)
        if responsible_fc is not None and fund.responsible_fc != responsible_fc:
            raise AccessDeniedError("The fund does not belong to the mission fund manager")
        if not await self._repository.lock(fund_id, mission_id):
            raise FundLockedError(fund_id)
        await self._session.refresh(fund)
        logger.info("Fund %s locked by mission %s", fund_id, mission_id)
        return fund

    async def release_from_mission(self, fund_id: UUID, mission_id: UUID) -> None:
        await self._repository.release(fund_id, mission_id)
        logger.info("Fund %s released by mission %s", fund_id, mission_id)

    async def _to_dtos(self, funds: list[Fund]) -> list[FundDTO]:
        holders = await self._repository.find_lock_holders(
            {fund.locked_by_mission_id for fund in funds if fund.locked_by_mission_id}
        )
        dtos = []
        for fund in funds:
            dto = FundDTO.model_validate(fund)
            holder = holders.get(fund.locked_by_mission_id)
            if holder is not None:
                dto = dto.model_copy(update={
                    "mission_subject": holder.subject,
                    "requested_amount": holder.estimated_cost,
                    "requester_name": f"{holder.name} {holder.surname}",
                })
            dtos.append(dto)
        return dtos

    async def _get_fund_or_throw(self, fund_id: UUID, *, for_update: bool = False) -> Fund:
        if for_update:
            fund = await self._repository.find_by_id_for_update(fund_id)
        else:
            fund = await self._repository.find_by_id(fund_id)
        if fund is None:
            raise FundNotFoundError(fund_id)
        return fund

    async def _get_active_user_or_throw(self, user_id: UUID) -> User:
        user = await self._user_repository.get_user_by_id(self._session, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if not user.is_active:
            raise AccessDeniedError(f"User {user_id} is inactive")
        return user

    @staticmethod
    def _validate_user_can_read(fund: Fund, user: User) -> None:
        if not user.is_superuser and fund.responsible_fc != user.fiscal_code:
            raise AccessDeniedError("User cannot access this fund")

    @staticmethod
    def _validate_user_is_responsible(fund: Fund, user: User) -> None:
        if fund.responsible_fc != user.fiscal_code:
            raise AccessDeniedError("Only the responsible can change this fund")

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self._session.commit()
        except BaseException:
            await self._session.rollback()
            raise