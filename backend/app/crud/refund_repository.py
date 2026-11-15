from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.refund_item import RefundItem
from app.db.refund_request import RefundRequest
from app.schemas.refund import RefundFilterDTO
from app.db.mission import Mission


class RefundRepository:
    async def find_by_id(
        self, session: AsyncSession, refund_id: UUID
    ) -> RefundRequest | None:
        stmt = (
            select(RefundRequest)
            .where(RefundRequest.id == refund_id)
            .options(selectinload(RefundRequest.items))
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def find_by_id_for_review(
        self, session: AsyncSession, refund_id: UUID
    ) -> RefundRequest | None:
        stmt = (
            select(RefundRequest)
            .where(RefundRequest.id == refund_id)
            .options(
                selectinload(RefundRequest.items),
                selectinload(RefundRequest.mission).selectinload(Mission.requester),
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def find_by_mission_id(
        self, session: AsyncSession, mission_id: UUID
    ) -> RefundRequest | None:
        stmt = (
            select(RefundRequest)
            .where(RefundRequest.mission_id == mission_id)
            .options(selectinload(RefundRequest.items))
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def save_request(
        self, session: AsyncSession, refund_request: RefundRequest
    ) -> RefundRequest:
        session.add(refund_request)
        await session.flush()
        return refund_request

    async def save_item(
        self, session: AsyncSession, item: RefundItem
    ) -> RefundItem:
        session.add(item)
        await session.flush()
        return item

    async def delete_item(
        self, session: AsyncSession, item: RefundItem
    ) -> None:
        await session.delete(item)
        await session.flush()

    async def get_filtered_refunds(self, session: AsyncSession, filters: RefundFilterDTO) -> list[RefundRequest]:
        query = (
            select(RefundRequest)
            .options(
                selectinload(RefundRequest.mission).selectinload(Mission.requester),
                selectinload(RefundRequest.items)
            )
        )

        if filters and filters.status:
            query = query.where(RefundRequest.status == filters.status)

        result = await session.execute(query)
        return list(result.scalars().unique().all())


refund_repository = RefundRepository()