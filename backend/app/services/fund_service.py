import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccessDeniedError,
    FundInUseError,
    FundNotFoundError,
    UserNotFoundError,
    FundAmountError,
)
from app.crud.fund_repository import FundRepository
from app.crud.user_repository import UserRepository
from app.db.fund import Fund
from app.db.models import User
from app.db.mission import Mission
from app.schemas.fund import FundCreateDTO, FundDTO, FundMissionDTO, FundUpdateDTO
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
        mission = await self._session.scalar(select(Mission).where(Mission.id == mission_id))
        if mission is None or mission.fund_id is None:
            return None
        fund = await self._get_fund_or_throw(mission.fund_id)

        if (
            user.is_superuser
            or fund.responsible_fc == user.fiscal_code
            or user.id in (mission.requester_id, mission.fund_manager_id)
        ):
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
            if data.amount < fund.committed_amount:
                raise FundAmountError(
                    fund_id,
                    f'Fund "{fund.name}" already has € {fund.committed_amount} committed to missions: '
                    f"its total amount cannot be lowered to € {data.amount}",
                )
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(fund, field, value)
            fund.updated_by = user.id
            saved = await self._repository.save(fund)
            result = (await self._to_dtos([saved]))[0]
        logger.info("Fund %s updated by user %s", fund_id, user_id)
        return result

    async def delete_fund(self, fund_id: UUID, user_id: UUID, *, force: bool = False) -> None:
        async with self._transaction():
            user = await self._get_active_user_or_throw(user_id)
            fund = await self._get_fund_or_throw(fund_id, for_update=True)
            self._validate_user_is_responsible(fund, user)
            if not force and await self._repository.is_funding_missions(fund.id):
                raise FundInUseError(fund.id)
            await self._repository.delete(fund)
        logger.info("Fund %s deleted by user %s", fund_id, user_id)

    async def reserve_for_mission(
        self, fund_id: UUID, mission_id: UUID, amount: Decimal, *, responsible_fc: str | None = None
    ) -> Fund:
        fund = await self._get_fund_or_throw(fund_id)
        if responsible_fc is not None and fund.responsible_fc != responsible_fc:
            raise AccessDeniedError("The fund does not belong to the mission fund manager")
        if not await self._repository.reserve(fund_id, amount):
            await self._session.refresh(fund)
            raise FundAmountError(
                fund_id,
                f'Fund "{fund.name}" has € {fund.amount - fund.committed_amount} available, '
                f"but the mission requires € {amount}",
            )
        await self._session.refresh(fund)
        logger.info("Fund %s: %s reserved by mission %s", fund_id, amount, mission_id)
        return fund

    async def release_from_mission(self, fund_id: UUID, mission_id: UUID, amount: Decimal) -> None:
        if not await self._repository.release(fund_id, amount):
            raise FundAmountError(
                fund_id, f"Cannot release € {amount}: it exceeds the amount committed on the fund"
            )
        logger.info("Fund %s: %s released by mission %s", fund_id, amount, mission_id)

    async def settle_mission(self, fund_id: UUID, mission_id: UUID, reserved: Decimal, spent: Decimal) -> None:
        if spent > reserved:
            raise FundAmountError(
                fund_id, f"Cannot charge € {spent}: the mission reserved only € {reserved} on the fund"
            )
        if not await self._repository.settle(fund_id, reserved, spent):
            raise FundAmountError(
                fund_id, f"Cannot settle € {spent} on the fund: the reserved amount is no longer available"
            )
        logger.info(
            "Fund %s: mission %s settled, %s charged and %s returned", fund_id, mission_id, spent, reserved - spent
        )

    async def _to_dtos(self, funds: list[Fund]) -> list[FundDTO]:
        missions = await self._repository.find_funded_missions({fund.id for fund in funds})
        return [
            FundDTO.model_validate(fund).model_copy(update={
                "missions": [
                    FundMissionDTO(
                        id=row.id,
                        subject=row.subject,
                        status=row.status,
                        estimated_cost=row.estimated_cost,
                        requester_name=f"{row.name} {row.surname}",
                        requested_at=row.created_at,
                    )
                    for row in missions.get(fund.id, [])
                ],
            })
            for fund in funds
        ]

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