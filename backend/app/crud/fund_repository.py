from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.pagination import paginate
from app.db.fund import Fund
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
            query = query.where(Fund.locked_by_mission_id.is_(None))

        query = query.order_by(Fund.name, Fund.id)
        return await paginate(self._session, query, request.page, request.size)

    async def lock(self, fund_id: UUID, mission_id: UUID) -> bool:
        # UPDATE condizionato: se due richieste arrivano insieme solo una trova il fondo libero.
        result = await self._session.execute(
            update(Fund)
            .where(Fund.id == fund_id, Fund.locked_by_mission_id.is_(None))
            .values(locked_by_mission_id=mission_id)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    async def release(self, fund_id: UUID, mission_id: UUID) -> None:
        await self._session.execute(
            update(Fund)
            .where(Fund.id == fund_id, Fund.locked_by_mission_id == mission_id)
            .values(locked_by_mission_id=None)
            .execution_options(synchronize_session=False)
        )

    async def save(self, fund: Fund) -> Fund:
        self._session.add(fund)
        await self._session.flush()
        await self._session.refresh(fund)
        return fund

    async def delete(self, fund: Fund) -> None:
        await self._session.delete(fund)
        await self._session.flush()
