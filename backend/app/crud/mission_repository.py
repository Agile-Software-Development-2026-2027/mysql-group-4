from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.crud.pagination import paginate
from app.db.mission import Mission
from app.schemas.page import Page, PageRequest


class MissionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_id(self, mission_id: UUID) -> Mission | None:
        return await self._session.get(Mission, mission_id)

    async def find_by_id_for_update(self, mission_id: UUID) -> Mission | None:
        query = (
            select(Mission)
            .where(Mission.id == mission_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(query)

    async def find_all(
        self,
        specification: ColumnElement[bool] | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[Mission]:
        request = page_request if page_request is not None else PageRequest()
        query = self._query(specification).order_by(Mission.starts_at, Mission.id)
        return await paginate(self._session, query, request.page, request.size)

    async def count(self, specification: ColumnElement[bool] | None = None) -> int:
        query = select(func.count()).select_from(self._query(specification).subquery())
        result = await self._session.scalar(query)
        return result if result is not None else 0

    async def save(self, mission: Mission) -> Mission:
        self._session.add(mission)
        await self._session.flush()
        await self._session.refresh(mission)
        return mission

    async def delete(self, mission: Mission) -> None:
        await self._session.delete(mission)
        await self._session.flush()

    @staticmethod
    def _query(specification: ColumnElement[bool] | None) -> Select[tuple[Mission]]:
        query = select(Mission)
        if specification is not None:
            query = query.where(specification)
        return query
