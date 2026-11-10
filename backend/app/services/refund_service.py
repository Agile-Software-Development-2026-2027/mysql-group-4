import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MissionStatus, RefundStatus
from app.core.exceptions import (
    AccessDeniedError,
    InvalidMissionStateError,
    InvalidRefundDecisionError,
    InvalidRefundRequestDateError,
    InvalidRefundStateError,
    MissionNotFoundError,
    RefundNotFoundError,
)
from app.crud.mission_repository import MissionRepository
from app.crud.refund_repository import RefundRepository
from app.db.models import User
from app.db.refund_request import RefundRequest
from app.schemas.refund import RefundApproveDTO, RefundRequestCreateDTO, RefundRequestDTO, RefundReviewDTO

logger = logging.getLogger(__name__)


class RefundService:
    def __init__(self, session: AsyncSession, refund_repository: RefundRepository, mission_repository: MissionRepository):
        self.session = session
        self.refund_repository = refund_repository
        self.mission_repository = mission_repository

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise

    async def create_refund_request(self, data: RefundRequestCreateDTO, user: User) -> RefundRequestDTO:
        async with self.transaction():
            mission = await self.mission_repository.find_by_id(data.mission_id)
            if not mission:
                raise MissionNotFoundError(data.mission_id)
            if mission.requester_id != user.id and not user.is_superuser:
                raise AccessDeniedError("Only the mission requester can create a refund request")
            if mission.status != MissionStatus.ACCEPTED:
                raise InvalidMissionStateError("A refund request can only be created for an accepted mission")
            if mission.ends_at > datetime.now():
                raise InvalidRefundRequestDateError("Refund request can only be created after the mission has ended")

            existing = await self.refund_repository.find_by_mission_id(self.session, mission.id)
            if existing is not None:
                raise InvalidMissionStateError("A refund request already exists for this mission")

            new_request = RefundRequest(**data.model_dump(), created_by=user.id, updated_by=user.id)
            saved = await self.refund_repository.save_request(self.session, new_request)
            await self.session.flush()
            loaded = await self.refund_repository.find_by_id(self.session, saved.id)
            result = RefundRequestDTO.model_validate(loaded)

        logger.info("Refund request %s created for mission %s by user %s", result.id, data.mission_id, user.id)
        return result

    async def get_refund_request_by_id(self, refund_id: UUID, user: User) -> RefundRequestDTO:
        refund = await self.refund_repository.find_by_id(self.session, refund_id)
        if not refund:
            raise RefundNotFoundError(refund_id)
        mission = await self.mission_repository.find_by_id(refund.mission_id)
        if mission and not user.is_superuser and mission.requester_id != user.id:
            raise AccessDeniedError("Only the requester or an administrator can view this refund request")
        return RefundRequestDTO.model_validate(refund)

    async def get_refund_for_review(self, refund_id: UUID, user: User) -> RefundReviewDTO:
        if not user.is_superuser:
            raise AccessDeniedError("Only administrators can review refund requests")
        refund = await self.refund_repository.find_by_id_for_review(self.session, refund_id)
        if not refund or refund.status == RefundStatus.DRAFT:
            raise RefundNotFoundError(refund_id)
        return RefundReviewDTO.model_validate(refund)

    async def approve_refund(self, refund_id: UUID, data: RefundApproveDTO, user: User) -> RefundReviewDTO:
        if not user.is_superuser:
            raise AccessDeniedError("Only administrators can approve refund requests")

        async with self.transaction():
            refund = await self.refund_repository.find_by_id(self.session, refund_id)
            if not refund or refund.status == RefundStatus.DRAFT:
                raise RefundNotFoundError(refund_id)
            if refund.status != RefundStatus.SUBMITTED:
                raise InvalidRefundStateError("Only submitted refund requests can be approved")

            items_by_id = {item.id: item for item in refund.items}
            for decision in data.items:
                item = items_by_id.get(decision.item_id)
                if item is None:
                    raise InvalidRefundDecisionError(f"Item {decision.item_id} does not belong to this refund request")
                item.reimbursed_amount = decision.reimbursed_amount
                item.admin_notes = decision.admin_notes
                item.updated_by = user.id

            refund.total_reimbursed_amount = sum(
                (item.reimbursed_amount or Decimal("0.00") for item in refund.items), Decimal("0.00"))
            refund.status = RefundStatus.APPROVED
            refund.approved_at = datetime.now(timezone.utc)
            refund.updated_by = user.id

        logger.info("Refund request %s approved by admin %s", refund_id, user.id)
        return await self.get_refund_for_review(refund_id, user)

    async def get_refund_request_by_mission(self, mission_id: UUID, user: User) -> RefundRequestDTO | None:
        mission = await self.mission_repository.find_by_id(mission_id)
        if not mission:
            raise MissionNotFoundError(mission_id)
        if not user.is_superuser and mission.requester_id != user.id:
            raise AccessDeniedError("Only the requester or an administrator can view this refund request")
        refund = await self.refund_repository.find_by_mission_id(self.session, mission_id)
        return RefundRequestDTO.model_validate(refund) if refund else None
