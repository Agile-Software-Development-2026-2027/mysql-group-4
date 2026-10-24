from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.mission.backend2frontend import MissionDTO
from app.schemas.mission.frontend2backend import (
    MissionCreateDTO,
    MissionFilterDTO,
    MissionUpdateDTO,
)
from app.schemas.page import Page, PageRequest


class MissionService(ABC):
    @abstractmethod
    async def get_mission_by_id(self, mission_id: UUID, user_id: UUID) -> MissionDTO:
        ...

    @abstractmethod
    async def get_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        ...

    @abstractmethod
    async def get_sent_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        ...

    @abstractmethod
    async def get_pending_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        ...

    @abstractmethod
    async def get_rejected_missions(
        self,
        user_id: UUID,
        filters: MissionFilterDTO | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[MissionDTO]:
        ...

    @abstractmethod
    async def create_mission(self, data: MissionCreateDTO, user_id: UUID) -> MissionDTO:
        ...

    @abstractmethod
    async def update_mission(
        self, mission_id: UUID, data: MissionUpdateDTO, user_id: UUID
    ) -> MissionDTO:
        ...

    @abstractmethod
    async def delete_mission(self, mission_id: UUID, user_id: UUID) -> None:
        ...

    @abstractmethod
    async def accept_mission(self, mission_id: UUID, user_id: UUID) -> MissionDTO:
        ...

    @abstractmethod
    async def reject_mission(self, mission_id: UUID, user_id: UUID) -> MissionDTO:
        ...
