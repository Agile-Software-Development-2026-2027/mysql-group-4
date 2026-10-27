from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.pagination import paginate
from app.db.mission import Mission
from app.schemas.mission import MissionFilterDTO
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
        filters: MissionFilterDTO | None = None,
        user_id: UUID | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[Mission]:
        request = page_request if page_request is not None else PageRequest()
        query = select(Mission)

        if user_id is not None:
            query = query.where(
                or_(Mission.requester_id == user_id, Mission.fund_manager_id == user_id)
            )

        if filters is not None:
            if filters.requester_id is not None:
                query = query.where(Mission.requester_id == filters.requester_id)
            if filters.fund_manager_id is not None:
                query = query.where(Mission.fund_manager_id == filters.fund_manager_id)
            if filters.status is not None:
                query = query.where(Mission.status == filters.status)
            if filters.mission_type is not None:
                query = query.where(Mission.mission_type == filters.mission_type)
            if filters.estimated_cost_min is not None:
                query = query.where(Mission.estimated_cost >= filters.estimated_cost_min)
            if filters.estimated_cost_max is not None:
                query = query.where(Mission.estimated_cost <= filters.estimated_cost_max)
            if filters.starts_at_from is not None:
                query = query.where(Mission.starts_at >= filters.starts_at_from)
            if filters.starts_at_to is not None:
                query = query.where(Mission.starts_at <= filters.starts_at_to)
            if filters.ends_at_from is not None:
                query = query.where(Mission.ends_at >= filters.ends_at_from)
            if filters.ends_at_to is not None:
                query = query.where(Mission.ends_at <= filters.ends_at_to)
            if filters.destination is not None:
                query = query.where(Mission.destination.icontains(filters.destination, autoescape=True))

        query = query.order_by(Mission.starts_at, Mission.id)
        return await paginate(self._session, query, request.page, request.size)

    async def save(self, mission: Mission) -> Mission:
        self._session.add(mission)
        await self._session.flush()
        await self._session.refresh(mission)
        return mission

    async def delete(self, mission: Mission) -> None:
        await self._session.delete(mission)
        await self._session.flush()
