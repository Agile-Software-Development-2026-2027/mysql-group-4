from datetime import datetime
from uuid import UUID

from app.core.exceptions import (
    AccessDeniedError,
    InvalidMissionPeriodError,
    InvalidMissionStateError,
    MissionNotFoundError,
)
from app.crud.mission_repository import MissionRepository
from app.db.enumerated import MissionStatus
from app.db.mission import Mission
from app.db.models import User


class MissionValidator:
    def __init__(self, repository: MissionRepository):
        self._repository = repository

    async def get_mission_or_throw(
        self, mission_id: UUID, *, for_update: bool = False
    ) -> Mission:
        if for_update:
            mission = await self._repository.find_by_id_for_update(mission_id)
        else:
            mission = await self._repository.find_by_id(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        return mission

    @staticmethod
    def validate_user_can_read(mission: Mission, user: User) -> None:
        if not user.is_superuser and user.id not in (
            mission.requester_id,
            mission.fund_manager_id,
        ):
            raise AccessDeniedError("User cannot access this mission")

    @staticmethod
    def validate_user_is_requester(mission: Mission, user: User) -> None:
        if mission.requester_id != user.id:
            raise AccessDeniedError("Only the requester can change this mission")

    @staticmethod
    def validate_user_is_fund_manager(mission: Mission, user: User) -> None:
        if mission.fund_manager_id != user.id:
            raise AccessDeniedError("Only the fund manager can decide this mission")

    @staticmethod
    def validate_mission_is_pending(mission: Mission) -> None:
        if mission.status is not MissionStatus.PENDING:
            raise InvalidMissionStateError("This operation requires a pending mission")

    @staticmethod
    def validate_period(starts_at: datetime, ends_at: datetime) -> None:
        if ends_at <= starts_at:
            raise InvalidMissionPeriodError("Mission end must be after its start")
