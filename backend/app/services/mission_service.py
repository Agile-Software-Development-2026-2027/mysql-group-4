import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.mission_repository import MissionRepository
from app.crud.specifications import MissionSpecifications
from app.db.enumerated import MissionStatus
from app.db.mission import Mission
from app.db.models import User
from app.schemas.mission import (
    MissionCreateDTO,
    MissionDTO,
    MissionFilterDTO,
    MissionUpdateDTO,
)
from app.schemas.page import Page, PageRequest
from app.validators.mission_validator import MissionValidator
from app.validators.user_validator import UserValidator

logger = logging.getLogger(__name__)


class MissionService:
    def __init__(
        self,
        session: AsyncSession,
        repository: MissionRepository,
        mission_validator: MissionValidator,
        user_validator: UserValidator,
    ):
        self._session = session
        self._repository = repository
        self._mission_validator = mission_validator
        self._user_validator = user_validator

    async def get_mission_by_id(self, mission_id: UUID, user_id: UUID) -> MissionDTO:
        user = await self._user_validator.get_active_user_or_throw(user_id)
        mission = await self._mission_validator.get_mission_or_throw(mission_id)
        self._mission_validator.validate_user_can_read(mission, user)
        return MissionDTO.model_validate(mission)

    async def get_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._user_validator.get_active_user_or_throw(user_id)
        return await self._find_missions(user, filters, page_request)

    async def get_sent_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._user_validator.get_active_user_or_throw(user_id)
        selected = self._with_filters(filters, requester_id=user.id)
        return await self._find_missions(user, selected, page_request)

    async def get_pending_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._user_validator.get_active_user_or_throw(user_id)
        selected = self._with_filters(filters, status=MissionStatus.PENDING)
        return await self._find_missions(user, selected, page_request)

    async def get_rejected_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        user = await self._user_validator.get_active_user_or_throw(user_id)
        selected = self._with_filters(filters, status=MissionStatus.REJECTED)
        return await self._find_missions(user, selected, page_request)

    async def create_mission(self, data: MissionCreateDTO, user_id: UUID) -> MissionDTO:
        async with self._transaction():
            user = await self._user_validator.get_active_user_or_throw(user_id)
            manager = await self._user_validator.get_active_user_or_throw(data.fund_manager_id)
            self._mission_validator.validate_period(data.starts_at, data.ends_at)
            mission = Mission(**data.model_dump())
            mission.requester = user
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
            user = await self._user_validator.get_active_user_or_throw(user_id)
            mission = await self._mission_validator.get_mission_or_throw(mission_id, for_update=True)
            self._mission_validator.validate_user_is_requester(mission, user)
            self._mission_validator.validate_mission_is_pending(mission)
            manager = await self._user_validator.get_active_user_or_throw(data.fund_manager_id)
            self._mission_validator.validate_period(data.starts_at, data.ends_at)
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(mission, field, value)
            mission.fund_manager = manager
            mission.updated_by = user.id
            saved = await self._repository.save(mission)
            result = MissionDTO.model_validate(saved)
        logger.info("Mission %s updated by user %s", mission_id, user_id)
        return result

    async def delete_mission(self, mission_id: UUID, user_id: UUID) -> None:
        async with self._transaction():
            user = await self._user_validator.get_active_user_or_throw(user_id)
            mission = await self._mission_validator.get_mission_or_throw(mission_id, for_update=True)
            self._mission_validator.validate_user_is_requester(mission, user)
            self._mission_validator.validate_mission_is_pending(mission)
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
            user = await self._user_validator.get_active_user_or_throw(user_id)
            mission = await self._mission_validator.get_mission_or_throw(mission_id, for_update=True)
            self._mission_validator.validate_user_is_fund_manager(mission, user)
            self._mission_validator.validate_mission_is_pending(mission)
            mission.status = status
            mission.updated_by = user.id
            saved = await self._repository.save(mission)
            result = MissionDTO.model_validate(saved)
        logger.info("Mission %s set to %s by user %s", mission_id, status.value, user_id)
        return result

    async def _find_missions(
        self,
        user: User,
        filters: MissionFilterDTO | None,
        page_request: PageRequest | None,
    ) -> Page[MissionDTO]:
        visible_to = None if user.is_superuser else user.id
        specification = MissionSpecifications.filter_missions(filters, visible_to)
        missions = await self._repository.find_all(specification, page_request)
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
