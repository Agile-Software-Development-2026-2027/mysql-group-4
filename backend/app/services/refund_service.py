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
from app.core.enums import ExpenseCategory, ExpenseSubtype, MissionStatus, RefundStatus
from app.core.exceptions import (
    AccessDeniedError,
    InvalidMissionStateError,
    InvalidRefundDecisionError,
    InvalidRefundRequestDateError,
    InvalidRefundStateError,
    MissionNotFoundError,
    RefundAmountExceededError,
    RefundItemCreateError,
    RefundNotFoundError,
    ResourceNotFoundError,
)
from app.crud.fund_repository import FundRepository
from app.crud.mission_repository import MissionRepository
from app.crud.refund_repository import RefundRepository
from app.db.models import User
from app.db.refund_item import RefundItem
from app.db.refund_request import RefundRequest
from app.schemas.page import Page, PageRequest
from app.schemas.receipt_ai import BoundingBoxDTO, ReceiptAutocompleteDTO
from app.schemas.refund import (
    RefundApproveDTO,
    RefundItemFilterDTO,
    RefundItemUpdateDTO,
    RefundItemCreateDTO,
    RefundItemDTO,
    RefundReceiptUploadDTO,
    RefundRequestCreateDTO,
    RefundRequestDTO,
    RefundReviewDTO,
    RefundFilterDTO,
    RefundOverviewDTO
)
from app.services.currency_service import CurrencyConversionService
from app.services.fund_service import FundService
from app.services.receipt_ai_service import ReceiptAIService

logger = logging.getLogger(__name__)

MAX_RECEIPT_FILE_SIZE = 10 * 1024 * 1024

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
    def __init__(
        self,
        session: AsyncSession,
        refund_repository: RefundRepository,
        mission_repository: MissionRepository,
        fund_service: FundService | None = None,
    ):
        self.session = session
        self.refund_repository = refund_repository
        self.mission_repository = mission_repository
        self.fund_service = fund_service or FundService(session, FundRepository(session))

    async def _ensure_within_estimate(self, refund_request: RefundRequest, total: Decimal) -> None:
        mission = await self.mission_repository.find_by_id(refund_request.mission_id)
        if mission and total > mission.estimated_cost:
            raise RefundAmountExceededError(
                f"The refund total (€ {total}) cannot exceed the mission estimated cost (€ {mission.estimated_cost})"
            )

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

    async def submit_refund_request(self, refund_id: UUID, user: User) -> RefundRequestDTO:
        async with self.transaction():
            refund = await self.refund_repository.find_by_id(self.session, refund_id)
            if not refund:
                raise RefundNotFoundError(refund_id)
            if refund.created_by != user.id:
                raise AccessDeniedError("Only the requester can submit this refund request")
            if refund.status != RefundStatus.DRAFT:
                raise InvalidRefundStateError("Only draft refund requests can be submitted")
            if not refund.items:
                raise InvalidRefundStateError("Cannot submit a refund request without expense items")
            if any(item.needs_review for item in refund.items):
                raise InvalidRefundStateError("Cannot submit a refund request while items are pending review")
            await self._ensure_within_estimate(refund, refund.total_requested_amount)

            refund.status = RefundStatus.SUBMITTED
            refund.submitted_at = datetime.now(timezone.utc)
            refund.updated_by = user.id

            await self.session.flush()
            await self.session.refresh(refund)
            loaded = await self.refund_repository.find_by_id(self.session, refund_id)
            result = RefundRequestDTO.model_validate(loaded)

        logger.info("Refund request %s submitted by user %s", refund_id, user.id)
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
                if decision.reimbursed_amount > item.requested_amount:
                    raise InvalidRefundDecisionError(
                        f"The reimbursed amount for item {item.id} cannot exceed the requested € {item.requested_amount}"
                    )
                item.reimbursed_amount = decision.reimbursed_amount
                item.admin_notes = decision.admin_notes
                item.updated_by = user.id

            refund.total_reimbursed_amount = sum(
                (item.reimbursed_amount or Decimal("0.00") for item in refund.items), Decimal("0.00"))
            mission = await self.mission_repository.find_by_id(refund.mission_id)
            if refund.total_reimbursed_amount > mission.estimated_cost:
                raise RefundAmountExceededError(
                    f"The reimbursed total (€ {refund.total_reimbursed_amount}) cannot exceed "
                    f"the mission estimated cost (€ {mission.estimated_cost})"
                )
            refund.status = RefundStatus.APPROVED
            refund.approved_at = datetime.now(timezone.utc)
            refund.updated_by = user.id
            mission.status = MissionStatus.COMPLETED

            if mission.fund_id is not None:
                await self.fund_service.settle_mission(
                    mission.fund_id, mission.id, mission.estimated_cost, refund.total_reimbursed_amount
                )

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
        if len(content) > MAX_RECEIPT_FILE_SIZE:
            raise RefundItemCreateError("Receipt file exceeds the maximum allowed size of 10MB.")

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
            await self._ensure_within_estimate(
                refund_request, refund_request.total_requested_amount + data.requested_amount
            )

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

    async def get_filtered_refunds(self, user: User, filters: RefundFilterDTO | None = None) -> list[RefundOverviewDTO]:
        if not user.is_superuser:
            raise AccessDeniedError("Only administrators can filter and view the refund overview.")

        if filters is None:
            filters = RefundFilterDTO()

        refunds = await self.refund_repository.get_filtered_refunds(self.session, filters)

        return [
            RefundOverviewDTO(
                id=r.id,
                status=r.status,
                requester_name=r.mission.requester.name,
                requester_surname=r.mission.requester.surname,
                subject=r.mission.subject,
                total_requested=r.total_requested_amount,
                total_reimbursed=r.total_reimbursed_amount,
                submitted_at=r.submitted_at,
                approved_at=r.approved_at
            ) for r in refunds
        ]

    async def get_refund_items(
        self,
        refund_id: UUID,
        user: User,
        filters: RefundItemFilterDTO | None,
        page_request: PageRequest,
    ) -> Page[RefundItemDTO]:
        refund = await self.refund_repository.find_by_id(self.session, refund_id)
        if not refund:
            raise RefundNotFoundError(refund_id)
        mission = await self.mission_repository.find_by_id(refund.mission_id)
        if mission and not user.is_superuser and mission.requester_id != user.id:
            raise AccessDeniedError("Only the requester or an administrator can view these refund items")

        page = await self.refund_repository.find_items_by_refund_id(
            self.session, refund_id, filters, page_request
        )
        return Page(
            content=[RefundItemDTO.model_validate(item) for item in page.content],
            total_elements=page.total_elements,
            number=page.number,
            size=page.size,
        )

    async def update_refund_item(
        self,
        refund_request_id: UUID,
        item_id: UUID,
        user: User,
        data: RefundItemUpdateDTO,
    ) -> RefundItemDTO:
        async with self.transaction():
            refund_request = await self.refund_repository.find_by_id(self.session, refund_request_id)
            if not refund_request:
                raise RefundNotFoundError(refund_request_id)
            if refund_request.created_by != user.id:
                raise AccessDeniedError("Only the requester can update a refund item.")
            if refund_request.status != RefundStatus.DRAFT:
                raise InvalidRefundStateError("You cannot update items of a non-draft refund request.")

            item = await self.refund_repository.find_item_by_id(self.session, refund_request_id, item_id)
            if not item:
                raise ResourceNotFoundError("RefundItem", item_id)

            updates = data.model_dump(exclude_unset=True)
            old_amount = item.requested_amount
            old_receipt_path = item.receipt_file_path
            for field, value in updates.items():
                setattr(item, field, value)
            item.updated_by = user.id
            item.needs_review = False

            if "requested_amount" in updates:
                new_total = refund_request.total_requested_amount + item.requested_amount - old_amount
                await self._ensure_within_estimate(refund_request, new_total)
                refund_request.total_requested_amount = new_total

            await self.session.flush()
            await self.session.refresh(item)
            result = RefundItemDTO.model_validate(item)

        if old_receipt_path and old_receipt_path != result.receipt_file_path:
            try:
                await anyio.to_thread.run_sync(
                    lambda: minio_client.remove_object(
                        bucket_name=settings.MINIO_BUCKET_NAME,
                        object_name=old_receipt_path,
                    )
                )
            except Exception as e:
                logger.warning("Could not delete replaced receipt file from MinIO: %s", e)

        return result

    async def delete_refund_item(
        self,
        refund_request_id: UUID,
        item_id: UUID,
        user: User,
    ) -> None:
        async with self.transaction():
            refund_request = await self.refund_repository.find_by_id(self.session, refund_request_id)
            if not refund_request:
                raise RefundNotFoundError(refund_request_id)
            if refund_request.created_by != user.id:
                raise AccessDeniedError("Only the requester can delete a refund item.")
            if refund_request.status != RefundStatus.DRAFT:
                raise InvalidRefundStateError("You cannot delete items of a non-draft refund request.")

            item = await self.refund_repository.find_item_by_id(self.session, refund_request_id, item_id)
            if not item:
                raise ResourceNotFoundError("RefundItem", item_id)

            refund_request.total_requested_amount -= item.requested_amount
            receipt_path = item.receipt_file_path

            await self.refund_repository.delete_item(self.session, item)

            if receipt_path:
                try:
                    await anyio.to_thread.run_sync(
                        lambda: minio_client.remove_object(
                            bucket_name=settings.MINIO_BUCKET_NAME,
                            object_name=receipt_path,
                        )
                    )
                except Exception as e:
                    logger.warning("Could not delete receipt file from MinIO: %s", e)

    async def _upload_receipt_bytes(
        self,
        refund_request_id: UUID,
        content: bytes,
        filename: str,
        content_type: str = "image/jpeg",
    ) -> RefundReceiptUploadDTO:
        object_name = f"refunds/{refund_request_id}/receipts/{uuid4()}_{filename}"
        file_stream = io.BytesIO(content)
        try:
            await anyio.to_thread.run_sync(
                lambda: minio_client.put_object(
                    bucket_name=settings.MINIO_BUCKET_NAME,
                    object_name=object_name,
                    data=file_stream,
                    length=len(content),
                    content_type=content_type,
                )
            )
        except S3Error as e:
            logger.error("Error saving receipt to MinIO: %s", e)
            raise RefundItemCreateError(f"Error during saving on MinIO: {str(e)}")

        return RefundReceiptUploadDTO(
            receipt_file_path=object_name,
            receipt_original_filename=filename,
        )

    def _build_batch_refund_item(
        self,
        refund_request_id: UUID,
        user_id: UUID,
        extracted: ReceiptAutocompleteDTO,
        upload_dto: RefundReceiptUploadDTO,
        fallback_start: datetime,
    ) -> RefundItem:
        category = extracted.category or ExpenseCategory.OTHER
        subtype = extracted.subtype
        itinerary_from = extracted.itinerary_from
        itinerary_to = extracted.itinerary_to

        starts_at = fallback_start
        if extracted.starts_at:
            try:
                starts_at = datetime.strptime(extracted.starts_at, "%Y-%m-%dT%H:%M")
            except ValueError:
                starts_at = fallback_start

        ends_at: datetime | None = None
        if extracted.ends_at:
            try:
                parsed_end = datetime.strptime(extracted.ends_at, "%Y-%m-%dT%H:%M")
                if parsed_end >= starts_at:
                    ends_at = parsed_end
            except ValueError:
                ends_at = None

        if category == ExpenseCategory.TRANSPORT:
            if not subtype or not itinerary_from or not itinerary_to or ends_at is None:
                category = ExpenseCategory.OTHER
                subtype = None
                itinerary_from = None
                itinerary_to = None
                ends_at = None
        elif category == ExpenseCategory.ACCOMMODATION:
            itinerary_from = None
            itinerary_to = None
            if not subtype or ends_at is None:
                category = ExpenseCategory.OTHER
                subtype = None
                ends_at = None
        elif category == ExpenseCategory.MEALS:
            itinerary_from = None
            itinerary_to = None
            ends_at = None
            if not subtype:
                subtype = ExpenseSubtype.MEALS_EXPENSE
        else:
            subtype = None
            itinerary_from = None
            itinerary_to = None
            ends_at = None

        raw_amount = extracted.converted_amount_eur or extracted.amount
        if raw_amount is None or raw_amount <= Decimal("0.00") or raw_amount > Decimal("10000.00"):
            requested_amount = Decimal("0.01")
        else:
            requested_amount = raw_amount.quantize(Decimal("0.01"))

        description = (extracted.description or extracted.merchant or "Pending review").strip()[:255]
        if not description:
            description = "Pending review"

        return RefundItem(
            refund_request_id=refund_request_id,
            category=category,
            subtype=subtype,
            itinerary_from=itinerary_from,
            itinerary_to=itinerary_to,
            starts_at=starts_at,
            ends_at=ends_at,
            requested_amount=requested_amount,
            currency="EUR",
            is_traceable=True,
            receipt_file_path=upload_dto.receipt_file_path,
            receipt_original_filename=upload_dto.receipt_original_filename,
            description=description,
            needs_review=True,
            created_by=user_id,
            updated_by=user_id,
        )

    async def process_batch_receipts(
        self,
        refund_request_id: UUID,
        file: UploadFile,
        boxes: list[BoundingBoxDTO],
        user: User,
        currency_service: CurrencyConversionService,
        receipt_ai_service: ReceiptAIService,
    ) -> list[RefundItemDTO]:
        if not boxes:
            raise RefundItemCreateError("At least one bounding box is required.")

        refund_request = await self.refund_repository.find_by_id(self.session, refund_request_id)
        if not refund_request:
            raise RefundNotFoundError(refund_request_id)
        if refund_request.created_by != user.id:
            raise AccessDeniedError("Only the requester can process batch receipts.")
        if refund_request.status != RefundStatus.DRAFT:
            raise RefundItemCreateError("Cannot add items to a non-draft refund request.")

        raw_bytes = await file.read()
        if not raw_bytes:
            raise RefundItemCreateError("Receipt file cannot be empty.")
        if len(raw_bytes) > MAX_RECEIPT_FILE_SIZE:
            raise RefundItemCreateError("Receipt file exceeds the maximum allowed size of 10MB.")

        content_type = (file.content_type or "").lower()
        filename_lower = (file.filename or "").lower()
        is_pdf = content_type == "application/pdf" or filename_lower.endswith(".pdf")

        pdf_pages: list[bytes] = []
        if is_pdf:
            try:
                pdf_pages = await anyio.to_thread.run_sync(receipt_ai_service.render_pdf_pages, raw_bytes)
            except Exception as exc:
                logger.warning("PDF rendering failed during batch processing: %s", exc)
                raise RefundItemCreateError("Unable to render PDF pages.")
            if not pdf_pages:
                raise RefundItemCreateError("Uploaded PDF contains no pages.")

        mission = await self.mission_repository.find_by_id(refund_request.mission_id)
        destination = mission.destination if mission else None
        hint_currency = await currency_service.resolve_currency_for_destination(destination)
        fallback_start = mission.starts_at if mission else datetime.now().replace(second=0, microsecond=0)
        base_stem = Path(file.filename).stem if file.filename else "receipt"

        prepared_items: list[RefundItem] = []
        for idx, box in enumerate(boxes, start=1):
            if is_pdf:
                if box.page < 0 or box.page >= len(pdf_pages):
                    raise RefundItemCreateError(f"Invalid page index {box.page} for PDF document.")
                source_bytes = pdf_pages[box.page]
            else:
                source_bytes = raw_bytes

            cropped_bytes = await anyio.to_thread.run_sync(receipt_ai_service.crop_receipt, source_bytes, box)
            crop_filename = f"{base_stem}_part_{idx}.jpg"
            upload_dto = await self._upload_receipt_bytes(
                refund_request_id=refund_request_id,
                content=cropped_bytes,
                filename=crop_filename,
                content_type="image/jpeg",
            )
            extracted = await receipt_ai_service.extract_receipt_from_bytes(
                cropped_bytes,
                is_pdf=False,
                hint_currency=hint_currency,
                hint_country=destination,
            )
            item = self._build_batch_refund_item(
                refund_request_id=refund_request_id,
                user_id=user.id,
                extracted=extracted,
                upload_dto=upload_dto,
                fallback_start=fallback_start,
            )
            prepared_items.append(item)

        created_dtos: list[RefundItemDTO] = []

        async with self.transaction():
            refund_request = await self.refund_repository.find_by_id(self.session, refund_request_id)
            for item in prepared_items:
                saved = await self.refund_repository.save_item(self.session, item)
                refund_request.total_requested_amount += item.requested_amount
                await self.session.flush()
                created_dtos.append(RefundItemDTO.model_validate(saved))

        return created_dtos