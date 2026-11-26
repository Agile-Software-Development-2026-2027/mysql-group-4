from decimal import Decimal
import json
import mimetypes
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import TypeAdapter, ValidationError

from app.api.deps import get_currency_service, get_receipt_ai_service, get_refund_service
from app.db.models import User
from app.schemas.currency import CurrencyConversionDTO, MissionCurrencyProfileDTO
from app.schemas.page import Page, PageRequest
from app.schemas.receipt_ai import BoundingBoxDTO, ReceiptAutocompleteDTO, ReceiptDetectionResponseDTO
from app.schemas.refund import (
    RefundApproveDTO,
    RefundItemCreateDTO,
    RefundItemDTO,
    RefundItemFilterDTO,
    RefundItemUpdateDTO,
    RefundReceiptUploadDTO,
    RefundRequestCreateDTO,
    RefundRequestDTO,
    RefundReviewDTO,
    RefundFilterDTO,
    RefundOverviewDTO
)
from app.security import current_active_user
from app.services.currency_service import CurrencyConversionService
from app.services.receipt_ai_service import ReceiptAIService
from app.services.refund_service import RefundService

refund_router = APIRouter(prefix="/refunds", tags=["refunds"])

RefundServiceDependency = Annotated[RefundService, Depends(get_refund_service)]
CurrencyServiceDependency = Annotated[CurrencyConversionService, Depends(get_currency_service)]
ReceiptAIServiceDependency = Annotated[ReceiptAIService, Depends(get_receipt_ai_service)]
CurrentUser = Annotated[User, Depends(current_active_user)]


def get_page_request(
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=5)] = 5,
) -> PageRequest:
    return PageRequest(page=page, size=size)


Pagination = Annotated[PageRequest, Depends(get_page_request)]


@refund_router.post("", response_model=RefundRequestDTO, status_code=status.HTTP_201_CREATED)
async def create_refund_request(refund_request: RefundRequestCreateDTO, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO:
    return await service.create_refund_request(refund_request, user)


@refund_router.get("/by-mission/{mission_id}", response_model=RefundRequestDTO | None, summary="Get refund request associated with a mission")
async def get_refund_by_mission(mission_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO | None:
    return await service.get_refund_request_by_mission(mission_id, user)


@refund_router.get("/convert-currency", response_model=CurrencyConversionDTO, status_code=status.HTTP_200_OK, summary="Convert foreign currency amount to EUR")
async def convert_currency_to_eur(
    user: CurrentUser,
    currency_service: CurrencyServiceDependency,
    amount: float = Query(..., gt=0),
    currency: str = Query(..., min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$"),
    issued_date: str = Query(
        ...,
        alias="issuedDate",
        min_length=10,
        max_length=10,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
) -> CurrencyConversionDTO:
    conversion = await currency_service.convert_to_eur(
        amount=Decimal(str(amount)),
        currency=currency,
        issued_date=issued_date,
    )
    if conversion is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to retrieve exchange rate for currency '{currency.upper()}'.",
        )
    return conversion


@refund_router.get("/{refund_id}/review", response_model=RefundReviewDTO, summary="Get refund request details for admin review")
async def get_refund_for_review(refund_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> RefundReviewDTO:
    return await service.get_refund_for_review(refund_id, user)


@refund_router.get("/{refund_id}", response_model=RefundRequestDTO, summary="Get refund request by ID")
async def get_refund_by_id(refund_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO:
    return await service.get_refund_request_by_id(refund_id, user)


@refund_router.patch("/{refund_id}/submit", response_model=RefundRequestDTO, summary="Submit a draft refund request")
async def submit_refund_request(
    refund_id: UUID,
    user: CurrentUser,
    service: RefundServiceDependency,
) -> RefundRequestDTO:
    return await service.submit_refund_request(refund_id, user)


@refund_router.patch("/{refund_id}/approve", response_model=RefundReviewDTO, summary="Approve a submitted refund request (admin only)")
async def approve_refund(refund_id: UUID, decisions: RefundApproveDTO, user: CurrentUser, service: RefundServiceDependency) -> RefundReviewDTO:
    return await service.approve_refund(refund_id, decisions, user)


@refund_router.post("/{refund_id}/receipts", response_model=RefundReceiptUploadDTO, status_code=status.HTTP_201_CREATED, summary="Upload receipt file to MinIO")
async def upload_receipt(refund_id: UUID, user: CurrentUser, service: RefundServiceDependency, file: UploadFile = File(...)) -> RefundReceiptUploadDTO:
    return await service.upload_receipt(refund_request_id=refund_id, file=file, user=user)


@refund_router.get("/{refund_id}/items/{item_id}/receipt", summary="Download the receipt of a refund item")
async def download_receipt(refund_id: UUID, item_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> Response:
    content, filename = await service.download_receipt(refund_request_id=refund_id, item_id=item_id, user=user)
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@refund_router.post("/{refund_id}/items", response_model=RefundItemDTO, status_code=status.HTTP_201_CREATED, summary="Create refund item")
async def create_refund_item(refund_id: UUID, user: CurrentUser, service: RefundServiceDependency, data: RefundItemCreateDTO) -> RefundItemDTO:
    return await service.create_refund_item(refund_request_id=refund_id, user=user, data=data)


@refund_router.post("/filter", response_model=list[RefundOverviewDTO], summary="Filter refunds by status (admin only)")
async def filter_refunds(
    user: CurrentUser,
    service: RefundServiceDependency,
    filters: RefundFilterDTO | None = None,
) -> list[RefundOverviewDTO]:
    return await service.get_filtered_refunds(user, filters)


@refund_router.post("/{refund_id}/items/filter", response_model=Page[RefundItemDTO], summary="Filter and paginate refund items of a refund request")
async def get_refund_items(
    refund_id: UUID,
    user: CurrentUser,
    service: RefundServiceDependency,
    page_request: Pagination,
    filters: RefundItemFilterDTO | None = None,
) -> Page[RefundItemDTO]:
    return await service.get_refund_items(refund_id=refund_id, user=user, filters=filters, page_request=page_request)


@refund_router.patch("/{refund_id}/items/{item_id}", response_model=RefundItemDTO, summary="Update a refund item")
async def update_refund_item(
    refund_id: UUID,
    item_id: UUID,
    user: CurrentUser,
    service: RefundServiceDependency,
    data: RefundItemUpdateDTO,
) -> RefundItemDTO:
    return await service.update_refund_item(refund_request_id=refund_id, item_id=item_id, user=user, data=data)


@refund_router.delete("/{refund_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a refund item")
async def delete_refund_item(
    refund_id: UUID,
    item_id: UUID,
    user: CurrentUser,
    service: RefundServiceDependency,
) -> None:
    await service.delete_refund_item(refund_request_id=refund_id, item_id=item_id, user=user)
@refund_router.get("/{refund_id}/currency-profile", response_model=MissionCurrencyProfileDTO, status_code=status.HTTP_200_OK, summary="Get default currency for a refund's mission destination")
async def get_refund_currency_profile(
    refund_id: UUID,
    user: CurrentUser,
    refund_service: RefundServiceDependency,
    currency_service: CurrencyServiceDependency,
) -> MissionCurrencyProfileDTO:
    refund_request = await refund_service.get_refund_request_by_id(refund_id, user)
    mission = await refund_service.mission_repository.find_by_id(refund_request.mission_id)
    destination = mission.destination if mission else None
    default_currency = await currency_service.resolve_currency_for_destination(destination)
    return MissionCurrencyProfileDTO(
        destination=destination,
        default_currency=default_currency,
    )


@refund_router.post(
    "/{refund_id}/receipts/extract",
    response_model=ReceiptAutocompleteDTO,
    status_code=status.HTTP_200_OK,
    summary="Extract structured expense fields from a receipt image via Receipt AI",
)
async def extract_receipt_fields(
    refund_id: UUID,
    user: CurrentUser,
    refund_service: RefundServiceDependency,
    currency_service: CurrencyServiceDependency,
    receipt_ai_service: ReceiptAIServiceDependency,
    file: UploadFile = File(...),
) -> ReceiptAutocompleteDTO:
    refund_request = await refund_service.get_refund_request_by_id(refund_id, user)
    mission = await refund_service.mission_repository.find_by_id(refund_request.mission_id)
    destination = mission.destination if mission else None
    hint_currency = await currency_service.resolve_currency_for_destination(destination)
    return await receipt_ai_service.extract_receipt(
        file=file,
        hint_currency=hint_currency,
        hint_country=destination,
    )


@refund_router.post(
    "/{refund_id}/receipts/detect",
    response_model=ReceiptDetectionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Detect individual receipt bounding boxes in a single image",
)
async def detect_receipt_boxes(
    refund_id: UUID,
    user: CurrentUser,
    refund_service: RefundServiceDependency,
    receipt_ai_service: ReceiptAIServiceDependency,
    file: UploadFile = File(...),
) -> ReceiptDetectionResponseDTO:
    await refund_service.get_refund_request_by_id(refund_id, user)
    return await receipt_ai_service.detect_receipt_boxes(file=file)


@refund_router.post(
    "/{refund_id}/receipts/batch-process",
    response_model=list[RefundItemDTO],
    status_code=status.HTTP_201_CREATED,
    summary="Crop receipts using confirmed bounding boxes, run OCR/AI, and create draft items pending review",
)
async def batch_process_receipts(
    refund_id: UUID,
    user: CurrentUser,
    refund_service: RefundServiceDependency,
    currency_service: CurrencyServiceDependency,
    receipt_ai_service: ReceiptAIServiceDependency,
    file: UploadFile = File(...),
    boxes: str = Form(...),
) -> list[RefundItemDTO]:
    try:
        parsed_boxes = TypeAdapter(list[BoundingBoxDTO]).validate_json(boxes)
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid boxes JSON payload: {exc}",
        )

    return await refund_service.process_batch_receipts(
        refund_request_id=refund_id,
        file=file,
        boxes=parsed_boxes,
        user=user,
        currency_service=currency_service,
        receipt_ai_service=receipt_ai_service,
    )