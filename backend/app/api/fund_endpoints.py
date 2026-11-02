from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_fund_service
from app.api.mission_endpoints import CurrentUser, Pagination
from app.schemas.fund import FundCreateDTO, FundDTO, FundUpdateDTO
from app.schemas.page import Page
from app.services.fund_service import FundService

fund_router = APIRouter(prefix="/funds", tags=["funds"])

FundServiceDependency = Annotated[FundService, Depends(get_fund_service)]


@fund_router.get("", response_model=Page[FundDTO])
async def get_funds(
    user: CurrentUser,
    service: FundServiceDependency,
    page_request: Pagination,
) -> Page[FundDTO]:
    return await service.get_funds(user.id, page_request)


@fund_router.get("/available", response_model=Page[FundDTO])
async def get_available_funds(
    user: CurrentUser,
    service: FundServiceDependency,
    page_request: Pagination,
) -> Page[FundDTO]:
    return await service.get_available_funds(user.id, page_request)


@fund_router.get("/{fund_id}", response_model=FundDTO)
async def get_fund_by_id(
    fund_id: UUID,
    user: CurrentUser,
    service: FundServiceDependency,
) -> FundDTO:
    return await service.get_fund_by_id(fund_id, user.id)


@fund_router.post("", response_model=FundDTO, status_code=status.HTTP_201_CREATED)
async def create_fund(
    data: FundCreateDTO,
    user: CurrentUser,
    service: FundServiceDependency,
) -> FundDTO:
    return await service.create_fund(data, user.id)


@fund_router.put("/{fund_id}", response_model=FundDTO)
async def update_fund(
    fund_id: UUID,
    data: FundUpdateDTO,
    user: CurrentUser,
    service: FundServiceDependency,
) -> FundDTO:
    return await service.update_fund(fund_id, data, user.id)


@fund_router.delete("/{fund_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fund(
    fund_id: UUID,
    user: CurrentUser,
    service: FundServiceDependency,
) -> Response:
    await service.delete_fund(fund_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
