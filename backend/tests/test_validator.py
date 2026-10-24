import pytest

from datetime import timedelta
from unittest.mock import create_autospec
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AccessDeniedError, InvalidMissionPeriodError, InvalidMissionStateError, MissionNotFoundError, UserNotFoundError
from app.crud.mission_repository import MissionRepository
from app.crud.user_repository import UserRepository
from app.db.enumerated import MissionStatus
from app.validators.mission_validator import MissionValidator
from app.validators.user_validator import UserValidator
from tests.factories import make_mission, make_user

class TestMissionValidator:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self):
        self.mission = make_mission()

    def test_requester_and_manager_can_read(self):
        for user_id in (self.mission.requester_id, self.mission.fund_manager_id):
            MissionValidator.validate_user_can_read(self.mission, make_user(id=user_id))

    def test_admin_can_read(self):
        MissionValidator.validate_user_can_read(self.mission, make_user(is_superuser=True))

    def test_unrelated_user_cannot_read(self):
        with pytest.raises(AccessDeniedError):
            MissionValidator.validate_user_can_read(self.mission, make_user())

    def test_only_requester_can_change(self):
        MissionValidator.validate_user_is_requester(self.mission, make_user(id=self.mission.requester_id))
        for user in (make_user(id=self.mission.fund_manager_id), make_user(is_superuser=True)):
            with pytest.raises(AccessDeniedError):
                MissionValidator.validate_user_is_requester(self.mission, user)

    def test_only_assigned_manager_can_decide(self):
        MissionValidator.validate_user_is_fund_manager(self.mission, make_user(id=self.mission.fund_manager_id))
        for user in (make_user(id=self.mission.requester_id), make_user(is_superuser=True)):
            with pytest.raises(AccessDeniedError):
                MissionValidator.validate_user_is_fund_manager(self.mission, user)

    def test_pending_is_required(self):
        MissionValidator.validate_mission_is_pending(self.mission)
        for status in (MissionStatus.ACCEPTED, MissionStatus.REJECTED):
            with pytest.raises(InvalidMissionStateError):
                MissionValidator.validate_mission_is_pending(make_mission(status=status))

    def test_end_must_be_strictly_after_start(self):
        start = self.mission.starts_at
        MissionValidator.validate_period(start, start + timedelta(seconds=1))
        for end in (start, start - timedelta(seconds=1)):
            with pytest.raises(InvalidMissionPeriodError):
                MissionValidator.validate_period(start, end)

class TestMissionLookup:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self):
        self.repository = create_autospec(MissionRepository, instance=True)
        self.validator = MissionValidator(self.repository)
        self.mission = make_mission()

    async def test_existing_mission_is_returned(self):
        self.repository.find_by_id.return_value = self.mission
        assert await self.validator.get_mission_or_throw(self.mission.id) is self.mission
        self.repository.find_by_id.assert_awaited_once_with(self.mission.id)
        self.repository.find_by_id_for_update.assert_not_awaited()

    async def test_write_lookup_uses_locking_repository_method(self):
        self.repository.find_by_id_for_update.return_value = self.mission
        assert await self.validator.get_mission_or_throw(self.mission.id, for_update=True) is self.mission
        self.repository.find_by_id_for_update.assert_awaited_once_with(self.mission.id)
        self.repository.find_by_id.assert_not_awaited()

    async def test_missing_mission_raises_for_both_lookup_modes(self):
        self.repository.find_by_id.return_value = None
        self.repository.find_by_id_for_update.return_value = None
        for locked in (False, True):
            with pytest.raises(MissionNotFoundError) as caught:
                await self.validator.get_mission_or_throw(self.mission.id, for_update=locked)
            assert caught.value.mission_id == self.mission.id

class TestUserValidator:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self):
        self.repository = create_autospec(UserRepository, instance=True)
        self.session = create_autospec(AsyncSession, instance=True)
        self.validator = UserValidator(self.repository, self.session)

    async def test_active_user_is_returned(self):
        user = make_user()
        self.repository.get_user_by_id.return_value = user
        assert await self.validator.get_active_user_or_throw(user.id) is user
        self.repository.get_user_by_id.assert_awaited_once_with(self.session, user.id)

    async def test_missing_user_raises_not_found(self):
        user_id = uuid4()
        self.repository.get_user_by_id.return_value = None
        with pytest.raises(UserNotFoundError) as caught:
            await self.validator.get_active_user_or_throw(user_id)
        assert caught.value.user_id == user_id

    async def test_inactive_user_cannot_act(self):
        user = make_user(is_active=False)
        self.repository.get_user_by_id.return_value = user
        with pytest.raises(AccessDeniedError):
            await self.validator.get_active_user_or_throw(user.id)
