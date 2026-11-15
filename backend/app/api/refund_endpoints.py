import mimetypes
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.api.deps import get_refund_service
from app.db.models import User
from app.schemas.page import Page, PageRequest
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
from app.services.refund_service import RefundService

refund_router = APIRouter(prefix="/refunds", tags=["refunds"])

RefundServiceDependency = Annotated[RefundService, Depends(get_refund_service)]
CurrentUser = Annotated[User, Depends(current_active_user)]


def get_page_request(
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageRequest:
    return PageRequest(page=page, size=size)


Pagination = Annotated[PageRequest, Depends(get_page_request)]


@refund_router.post("", response_model=RefundRequestDTO, status_code=status.HTTP_201_CREATED)
async def create_refund_request(refund_request: RefundRequestCreateDTO, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO:
    return await service.create_refund_request(refund_request, user)


@refund_router.get("/by-mission/{mission_id}", response_model=RefundRequestDTO | None, summary="Get refund request associated with a mission")
async def get_refund_by_mission(mission_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO | None:
    return await service.get_refund_request_by_mission(mission_id, user)


@refund_router.get("/{refund_id}/review", response_model=RefundReviewDTO, summary="Get refund request details for admin review")
async def get_refund_for_review(refund_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> RefundReviewDTO:
    return await service.get_refund_for_review(refund_id, user)


@refund_router.get("/{refund_id}", response_model=RefundRequestDTO, summary="Get refund request by ID")
async def get_refund_by_id(refund_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO:
    return await service.get_refund_request_by_id(refund_id, user)


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