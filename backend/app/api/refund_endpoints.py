from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_refund_service
from app.db.models import User
from app.schemas.refund import RefundRequestCreateDTO, RefundRequestDTO
from app.security import current_active_user
from app.services.refund_service import RefundService

refund_router = APIRouter(prefix="/refunds", tags=["refunds"])

RefundServiceDependency = Annotated[RefundService, Depends(get_refund_service)]
CurrentUser = Annotated[User, Depends(current_active_user)]


@refund_router.post("", response_model=RefundRequestDTO, status_code=status.HTTP_201_CREATED)
async def create_refund_request(refund_request: RefundRequestCreateDTO, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO:
    return await service.create_refund_request(refund_request, user)


@refund_router.get("/by-mission/{mission_id}", response_model=RefundRequestDTO | None, summary="Get refund request associated with a mission")
async def get_refund_by_mission(mission_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO | None:
    return await service.get_refund_request_by_mission(mission_id, user)


@refund_router.get("/{refund_id}", response_model=RefundRequestDTO, summary="Get refund request by ID")
async def get_refund_by_id(refund_id: UUID, user: CurrentUser, service: RefundServiceDependency) -> RefundRequestDTO:
    return await service.get_refund_request_by_id(refund_id, user)
