from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import RefundStatus
from app.crud.pagination import paginate
from app.db.refund_item import RefundItem
from app.db.refund_request import RefundRequest
from app.schemas.refund import RefundFilterDTO
from app.db.mission import Mission
from app.schemas.page import Page, PageRequest
from app.schemas.refund import RefundItemFilterDTO


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

    async def find_approved_amount_by_mission_id(
        self, session: AsyncSession, mission_id: UUID
    ) -> Decimal | None:
        stmt = select(RefundRequest.total_reimbursed_amount).where(
            RefundRequest.mission_id == mission_id,
            RefundRequest.status == RefundStatus.APPROVED,
        )
        return await session.scalar(stmt)

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

    async def find_items_by_refund_id(
        self,
        session: AsyncSession,
        refund_id: UUID,
        filters: RefundItemFilterDTO | None,
        page_request: PageRequest,
    ) -> Page[RefundItem]:
        stmt = select(RefundItem).where(RefundItem.refund_request_id == refund_id)

        if filters and filters.categories:
            stmt = stmt.where(RefundItem.category.in_(filters.categories))

        if filters and filters.sort_by_amount == "asc":
            stmt = stmt.order_by(RefundItem.requested_amount.asc(), RefundItem.created_at.asc())
        elif filters and filters.sort_by_amount == "desc":
            stmt = stmt.order_by(RefundItem.requested_amount.desc(), RefundItem.created_at.asc())
        else:
            stmt = stmt.order_by(RefundItem.created_at.asc())

        return await paginate(session, stmt, page=page_request.page, size=page_request.size)

    async def find_item_by_id(
        self, session: AsyncSession, refund_id: UUID, item_id: UUID
    ) -> RefundItem | None:
        stmt = select(RefundItem).where(
            RefundItem.id == item_id,
            RefundItem.refund_request_id == refund_id,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

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

    async def find_unseen_approved_for_requester(
        self, session: AsyncSession, user_id: UUID
    ) -> list[RefundRequest]:
        stmt = (
            select(RefundRequest)
            .join(Mission, RefundRequest.mission_id == Mission.id)
            .where(
                Mission.requester_id == user_id,
                RefundRequest.status == RefundStatus.APPROVED,
                RefundRequest.seen_by_requester.is_(False),
            )
            .options(
                selectinload(RefundRequest.mission),
                selectinload(RefundRequest.items),
            )
            .order_by(RefundRequest.approved_at.desc(), RefundRequest.updated_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().unique().all())

    async def mark_seen_for_requester(
        self, session: AsyncSession, user_id: UUID, refund_ids: list[UUID]
    ) -> None:
        if not refund_ids:
            return
        owned_mission_ids = select(Mission.id).where(Mission.requester_id == user_id)
        stmt = (
            update(RefundRequest)
            .where(
                RefundRequest.id.in_(refund_ids),
                RefundRequest.mission_id.in_(owned_mission_ids),
                RefundRequest.status == RefundStatus.APPROVED,
            )
            .values(seen_by_requester=True)
        )
        await session.execute(stmt)

refund_repository = RefundRepository()