from collections.abc import Collection
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Row, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.pagination import paginate
from app.db.fund import Fund
from app.db.mission import Mission
from app.db.models import User
from app.schemas.page import Page, PageRequest


class FundRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_id(self, fund_id: UUID) -> Fund | None:
        return await self._session.get(Fund, fund_id)

    async def find_by_id_for_update(self, fund_id: UUID) -> Fund | None:
        query = (
            select(Fund)
            .where(Fund.id == fund_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(query)

    async def find_all(
        self,
        responsible_fc: str | None = None,
        available_only: bool = False,
        page_request: PageRequest | None = None,
    ) -> Page[Fund]:
        request = page_request if page_request is not None else PageRequest()
        query = select(Fund)

        if responsible_fc is not None:
            query = query.where(Fund.responsible_fc == responsible_fc)
        if available_only:
            query = query.where(Fund.amount > Fund.committed_amount)

        query = query.order_by(Fund.name, Fund.id)
        return await paginate(self._session, query, request.page, request.size)

    async def find_funded_missions(self, fund_ids: Collection[UUID]) -> dict[UUID, list[Row]]:
        if not fund_ids:
            return {}
        result = await self._session.execute(
            select(
                Mission.fund_id, Mission.id, Mission.subject, Mission.status,
                Mission.estimated_cost, Mission.created_at, User.name, User.surname,
            )
            .join(User, User.id == Mission.requester_id)
            .where(Mission.fund_id.in_(fund_ids))
            .order_by(Mission.created_at, Mission.id)
        )
        missions: dict[UUID, list[Row]] = {}
        for row in result:
            missions.setdefault(row.fund_id, []).append(row)
        return missions

    async def is_funding_missions(self, fund_id: UUID) -> bool:
        return bool(await self._session.scalar(select(exists().where(Mission.fund_id == fund_id))))

    async def reserve(self, fund_id: UUID, amount: Decimal) -> bool:
        result = await self._session.execute(
            update(Fund)
            .where(Fund.id == fund_id, Fund.amount - Fund.committed_amount >= amount)
            .values(committed_amount=Fund.committed_amount + amount)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    async def release(self, fund_id: UUID, amount: Decimal) -> bool:
        result = await self._session.execute(
            update(Fund)
            .where(Fund.id == fund_id, Fund.committed_amount >= amount)
            .values(committed_amount=Fund.committed_amount - amount)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    async def save(self, fund: Fund) -> Fund:
        self._session.add(fund)
        await self._session.flush()
        await self._session.refresh(fund)
        return fund

    async def delete(self, fund: Fund) -> None:
        await self._session.delete(fund)
        await self._session.flush()
