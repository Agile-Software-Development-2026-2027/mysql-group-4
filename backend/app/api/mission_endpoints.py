from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.db.models import User
from app.schemas.mission import (
    MissionCreateDTO,
    MissionDTO,
    MissionFilterDTO,
    MissionUpdateDTO,
)
from app.schemas.page import Page, PageRequest
from app.security import current_active_user
from app.services.dependencies import get_mission_service
from app.services.mission_service import MissionService

mission_router = APIRouter(prefix="/missions", tags=["missions"])

CurrentUser = Annotated[User, Depends(current_active_user)]
MissionServiceDependency = Annotated[MissionService, Depends(get_mission_service)]


def get_page_request(
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageRequest:
    return PageRequest(page=page, size=size)


Pagination = Annotated[PageRequest, Depends(get_page_request)]


@mission_router.post("/filter", response_model=Page[MissionDTO])
async def get_missions(
    user: CurrentUser,
    service: MissionServiceDependency,
    page_request: Pagination,
    filters: MissionFilterDTO | None = None,
) -> Page[MissionDTO]:
    return await service.get_missions(user.id, filters, page_request)


@mission_router.post("/sent/filter", response_model=Page[MissionDTO])
async def get_sent_missions(
    user: CurrentUser,
    service: MissionServiceDependency,
    page_request: Pagination,
    filters: MissionFilterDTO | None = None,
) -> Page[MissionDTO]:
    return await service.get_sent_missions(user.id, filters, page_request)


@mission_router.post("/pending/filter", response_model=Page[MissionDTO])
async def get_pending_missions(
    user: CurrentUser,
    service: MissionServiceDependency,
    page_request: Pagination,
    filters: MissionFilterDTO | None = None,
) -> Page[MissionDTO]:
    return await service.get_pending_missions(user.id, filters, page_request)


@mission_router.post("/rejected/filter", response_model=Page[MissionDTO])
async def get_rejected_missions(
    user: CurrentUser,
    service: MissionServiceDependency,
    page_request: Pagination,
    filters: MissionFilterDTO | None = None,
) -> Page[MissionDTO]:
    return await service.get_rejected_missions(user.id, filters, page_request)


@mission_router.get("/{mission_id}", response_model=MissionDTO)
async def get_mission_by_id(
    mission_id: UUID,
    user: CurrentUser,
    service: MissionServiceDependency,
) -> MissionDTO:
    return await service.get_mission_by_id(mission_id, user.id)


@mission_router.post("", response_model=MissionDTO, status_code=status.HTTP_201_CREATED)
async def create_mission(
    data: MissionCreateDTO,
    user: CurrentUser,
    service: MissionServiceDependency,
) -> MissionDTO:
    return await service.create_mission(data, user.id)


@mission_router.put("/{mission_id}", response_model=MissionDTO)
async def update_mission(
    mission_id: UUID,
    data: MissionUpdateDTO,
    user: CurrentUser,
    service: MissionServiceDependency,
) -> MissionDTO:
    return await service.update_mission(mission_id, data, user.id)


@mission_router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mission(
    mission_id: UUID,
    user: CurrentUser,
    service: MissionServiceDependency,
) -> Response:
    await service.delete_mission(mission_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@mission_router.patch("/{mission_id}/accept", response_model=MissionDTO)
async def accept_mission(
    mission_id: UUID,
    user: CurrentUser,
    service: MissionServiceDependency,
) -> MissionDTO:
    return await service.accept_mission(mission_id, user.id)


@mission_router.patch("/{mission_id}/reject", response_model=MissionDTO)
async def reject_mission(
    mission_id: UUID,
    user: CurrentUser,
    service: MissionServiceDependency,
) -> MissionDTO:
    return await service.reject_mission(mission_id, user.id)
