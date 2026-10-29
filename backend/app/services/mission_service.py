import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccessDeniedError,
    InvalidMissionStateError,
    MissionNotFoundError,
    UserNotFoundError,
)
from app.crud.mission_repository import MissionRepository
from app.crud.user_repository import UserRepository
from app.core.enums import MissionStatus
from app.db.mission import Mission
from app.db.models import User
from app.schemas.mission import (
    MissionCreateDTO,
    MissionDTO,
    MissionFilterDTO,
    MissionUpdateDTO,
)
from app.schemas.page import Page, PageRequest

logger = logging.getLogger(__name__)


class MissionService:
    def __init__(
        self,
        session: AsyncSession,
        repository: MissionRepository,
        user_repository: UserRepository | None = None,
    ):
        self._session = session
        self._repository = repository
        self._user_repository = user_repository or UserRepository()

    async def get_mission_by_id(self, mission_id: UUID, user_id: UUID) -> MissionDTO:
        user = await self._get_active_user_or_throw(user_id)
        mission = await self._get_mission_or_throw(mission_id)
        self._validate_user_can_read(mission, user)
        return MissionDTO.model_validate(mission)

    async def get_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._get_active_user_or_throw(user_id)
        return await self._find_missions(user, filters, page_request)

    async def get_sent_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._get_active_user_or_throw(user_id)
        selected = self._with_filters(filters, requester_id=user.id)
        return await self._find_missions(user, selected, page_request)

    async def get_pending_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._get_active_user_or_throw(user_id)
        selected = self._with_filters(filters, status=MissionStatus.PENDING)
        return await self._find_missions(user, selected, page_request)

    async def get_rejected_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._get_active_user_or_throw(user_id)
        selected = self._with_filters(filters, status=MissionStatus.REJECTED)
        return await self._find_missions(user, selected, page_request)

    async def get_missions_to_approve(
            self,
            user_id: UUID,
            filters: MissionFilterDTO | None = None,
            page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._get_active_user_or_throw(user_id)
        selected = self._with_filters(
            filters, fund_manager_id=user.id, status=MissionStatus.PENDING
        )
        return await self._find_missions(user, selected, page_request)

    async def create_mission(self, data: MissionCreateDTO, user_id: UUID) -> MissionDTO:
        async with self._transaction():
            user = await self._get_active_user_or_throw(user_id)
            manager = await self._get_active_user_or_throw(data.fund_manager_id)
            mission = Mission(**data.model_dump())
            mission.requester_id = user.id
            mission.requester = user
            mission.fund_manager_id = manager.id
            mission.fund_manager = manager
            mission.status = MissionStatus.PENDING
            mission.created_by = user.id
            mission.updated_by = user.id
            saved = await self._repository.save(mission)
            result = MissionDTO.model_validate(saved)
        logger.info("Mission %s created by user %s", result.id, user_id)
        return result

    async def update_mission(
        self, mission_id: UUID, data: MissionUpdateDTO, user_id: UUID
    ) -> MissionDTO:
        async with self._transaction():
            user = await self._get_active_user_or_throw(user_id)
            if not user.is_superuser:
                raise AccessDeniedError("Only administrators can modify missions")
            mission = await self._get_mission_or_throw(mission_id, for_update=True)
            self._validate_mission_is_pending(mission)
            manager = await self._get_active_user_or_throw(data.fund_manager_id)
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(mission, field, value)
            mission.fund_manager_id = manager.id
            mission.fund_manager = manager
            mission.updated_by = user.id
            saved = await self._repository.save(mission)
            result = MissionDTO.model_validate(saved)
        logger.info("Mission %s updated by user %s", mission_id, user_id)
        return result

    async def delete_mission(self, mission_id: UUID, user_id: UUID) -> None:
        async with self._transaction():
            user = await self._get_active_user_or_throw(user_id)
            mission = await self._get_mission_or_throw(mission_id, for_update=True)
            self._validate_user_is_requester(mission, user)
            self._validate_mission_is_pending(mission)
            await self._repository.delete(mission)
        logger.info("Mission %s deleted by user %s", mission_id, user_id)

    async def accept_mission(self, mission_id: UUID, user_id: UUID) -> MissionDTO:
        return await self._decide_mission(mission_id, user_id, MissionStatus.ACCEPTED)

    async def reject_mission(self, mission_id: UUID, user_id: UUID) -> MissionDTO:
        return await self._decide_mission(mission_id, user_id, MissionStatus.REJECTED)

    async def _decide_mission(
        self, mission_id: UUID, user_id: UUID, status: MissionStatus
    ) -> MissionDTO:
        async with self._transaction():
            user = await self._get_active_user_or_throw(user_id)
            mission = await self._get_mission_or_throw(mission_id, for_update=True)
            self._validate_user_is_fund_manager(mission, user)
            self._validate_mission_is_pending(mission)
            mission.status = status
            mission.updated_by = user.id
            saved = await self._repository.save(mission)
            result = MissionDTO.model_validate(saved)
        logger.info("Mission %s set to %s by user %s", mission_id, status.value, user_id)
        return result

    async def _get_mission_or_throw(
        self, mission_id: UUID, *, for_update: bool = False
    ) -> Mission:
        if for_update:
            mission = await self._repository.find_by_id_for_update(mission_id)
        else:
            mission = await self._repository.find_by_id(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        return mission

    async def _get_active_user_or_throw(self, user_id: UUID) -> User:
        user = await self._user_repository.get_user_by_id(self._session, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if not user.is_active:
            raise AccessDeniedError(f"User {user_id} is inactive")
        return user

    @staticmethod
    def _validate_user_can_read(mission: Mission, user: User) -> None:
        if not user.is_superuser and user.id not in (
            mission.requester_id,
            mission.fund_manager_id,
        ):
            raise AccessDeniedError("User cannot access this mission")

    @staticmethod
    def _validate_user_is_requester(mission: Mission, user: User) -> None:
        if mission.requester_id != user.id:
            raise AccessDeniedError("Only the requester can change this mission")

    @staticmethod
    def _validate_user_is_fund_manager(mission: Mission, user: User) -> None:
        if mission.fund_manager_id != user.id:
            raise AccessDeniedError("Only the fund manager can decide this mission")

    @staticmethod
    def _validate_mission_is_pending(mission: Mission) -> None:
        if mission.status is not MissionStatus.PENDING:
            raise InvalidMissionStateError("This operation requires a pending mission")

    async def _find_missions(
        self,
        user: User,
        filters: MissionFilterDTO | None,
        page_request: PageRequest | None,
    ) -> Page[MissionDTO]:
        visible_to = None if user.is_superuser else user.id
        missions = await self._repository.find_all(
            filters=filters,
            user_id=visible_to,
            page_request=page_request,
        )
        logger.debug("Found %s missions for user %s", missions.total_elements, user.id)
        return missions.map(MissionDTO.model_validate)

    @staticmethod
    def _with_filters(filters: MissionFilterDTO | None, **overrides: object) -> MissionFilterDTO:
        values = filters.model_dump() if filters is not None else {}
        return MissionFilterDTO.model_validate(values | overrides)

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self._session.commit()
        except BaseException:
            await self._session.rollback()
            raise