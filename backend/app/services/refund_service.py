import io
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import anyio
from fastapi import UploadFile
from minio import Minio
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import MissionStatus, RefundStatus
from app.core.exceptions import (
    AccessDeniedError,
    InvalidMissionStateError,
    InvalidRefundDecisionError,
    InvalidRefundRequestDateError,
    InvalidRefundStateError,
    MissionNotFoundError,
    RefundItemCreateError,
    RefundNotFoundError,
    ResourceNotFoundError,
)
from app.crud.mission_repository import MissionRepository
from app.crud.refund_repository import RefundRepository
from app.db.models import User
from app.db.refund_item import RefundItem
from app.db.refund_request import RefundRequest
from app.schemas.refund import (
    RefundApproveDTO,
    RefundItemCreateDTO,
    RefundItemDTO,
    RefundReceiptUploadDTO,
    RefundRequestCreateDTO,
    RefundRequestDTO,
    RefundReviewDTO,
)

logger = logging.getLogger(__name__)

minio_client = Minio(
    endpoint=settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


def _ensure_bucket_exists():
    try:
        if not minio_client.bucket_exists(settings.MINIO_BUCKET_NAME):
            minio_client.make_bucket(settings.MINIO_BUCKET_NAME)
    except Exception as e:
        logger.warning("[MinIO] Warning: %s", e)


_ensure_bucket_exists()


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
            mission = await self.mission_repository.find_by_id(refund.mission_id)
            mission.status = MissionStatus.COMPLETED

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

    async def upload_receipt(self, refund_request_id: UUID, file: UploadFile, user: User) -> RefundReceiptUploadDTO:
        refund_request = await self.refund_repository.find_by_id(self.session, refund_request_id)
        if not refund_request:
            raise RefundNotFoundError(refund_request_id)
        if refund_request.created_by != user.id:
            raise AccessDeniedError("Only the requester can upload receipts to this refund request")
        if refund_request.status != RefundStatus.DRAFT:
            raise RefundItemCreateError("Cannot upload receipts to an already submitted or approved refund request.")

        safe_original_filename = Path(file.filename).name if file.filename else f"receipt_{uuid4()}.pdf"
        lower_name = safe_original_filename.lower()
        allowed_extensions = (".pdf", ".jpg", ".jpeg", ".png", ".webp")
        if not lower_name.endswith(allowed_extensions):
            raise RefundItemCreateError("Only PDF, JPEG, PNG, or WEBP receipt files are accepted.")

        content = await file.read()
        if not content:
            raise RefundItemCreateError("Receipt file cannot be empty.")

        object_name = f"refunds/{refund_request_id}/receipts/{uuid4()}_{safe_original_filename}"
        file_stream = io.BytesIO(content)

        try:
            await anyio.to_thread.run_sync(
                lambda: minio_client.put_object(
                    bucket_name=settings.MINIO_BUCKET_NAME,
                    object_name=object_name,
                    data=file_stream,
                    length=len(content),
                    content_type=file.content_type or "application/octet-stream",
                )
            )
        except S3Error as e:
            logger.error("Error saving receipt to MinIO: %s", e)
            raise RefundItemCreateError(f"Error during saving on MinIO: {str(e)}")

        return RefundReceiptUploadDTO(
            receipt_file_path=object_name,
            receipt_original_filename=safe_original_filename,
        )

    async def download_receipt(self, refund_request_id: UUID, item_id: UUID, user: User) -> tuple[bytes, str]:
        refund_request = await self.refund_repository.find_by_id(self.session, refund_request_id)
        if not refund_request:
            raise RefundNotFoundError(refund_request_id)
        if not user.is_superuser and refund_request.created_by != user.id:
            raise AccessDeniedError("Only the requester or an administrator can view this receipt")

        item = next((item for item in refund_request.items if item.id == item_id), None)
        if item is None:
            raise ResourceNotFoundError("RefundItem", item_id)

        try:
            response = await anyio.to_thread.run_sync(
                lambda: minio_client.get_object(settings.MINIO_BUCKET_NAME, item.receipt_file_path)
            )
            content = response.read()
            response.close()
            response.release_conn()
            return content, item.receipt_original_filename
        except S3Error:
            raise ResourceNotFoundError("Receipt", item_id)

    async def create_refund_item(self, refund_request_id: UUID, user: User, data: RefundItemCreateDTO) -> RefundItemDTO:
        async with self.transaction():
            refund_request = await self.refund_repository.find_by_id(self.session, refund_request_id)
            if not refund_request:
                raise RefundNotFoundError(refund_request_id)
            if refund_request.created_by != user.id:
                raise AccessDeniedError("Only the requester can add a refund item.")

            if refund_request.status != RefundStatus.DRAFT:
                raise RefundItemCreateError("You cannot add new items to an already submitted / accepted refund request.")

            refund_item = RefundItem(
                **data.model_dump(),
                refund_request_id=refund_request_id,
                created_by=user.id,
                updated_by=user.id,
            )
            saved = await self.refund_repository.save_item(self.session, refund_item)
            refund_request.total_requested_amount += data.requested_amount
            await self.session.flush()

            return RefundItemDTO.model_validate(saved)

