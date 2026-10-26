import pytest

from unittest.mock import create_autospec, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AccessDeniedError, InvalidMissionPeriodError, InvalidMissionStateError
from app.crud.mission_repository import MissionRepository
from app.db.enumerated import MissionStatus
from app.schemas.mission import MissionFilterDTO, MissionUpdateDTO
from app.schemas.page import Page, PageRequest
from app.services.mission_mapper_service import MissionMapperService
from app.services.mission_service_impl import MissionServiceImpl
from app.validators.mission_validator import MissionValidator
from app.validators.user_validator import UserValidator
from tests.factories import make_create_data, make_mission, make_user

class TestMissionService:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self):
        self.user = make_user()
        self.manager = make_user()
        self.mission = make_mission(requester_id=self.user.id, fund_manager_id=self.manager.id)
        self.data = make_create_data(fund_manager_id=self.manager.id)
        self.session = create_autospec(AsyncSession, instance=True)
        self.repository = create_autospec(MissionRepository, instance=True)
        self.validator = create_autospec(MissionValidator, instance=True)
        self.users = create_autospec(UserValidator, instance=True)
        self.mapper = create_autospec(MissionMapperService, instance=True)
        self.users.get_active_user_or_throw.side_effect = lambda user_id: {self.user.id: self.user, self.manager.id: self.manager}[user_id]
        self.validator.get_mission_or_throw.return_value = self.mission
        self.repository.save.side_effect = lambda mission: mission
        self.dto = MissionMapperService.convert_to_dto(self.mission)
        self.mapper.convert_to_dto.return_value = self.dto
        self.mapper.convert_to_entity.return_value = self.mission
        self.service = MissionServiceImpl(self.session, self.repository, self.validator, self.users, self.mapper)

    async def test_get_by_id_checks_visibility_before_mapping(self):
        assert await self.service.get_mission_by_id(self.mission.id, self.user.id) is self.dto
        self.validator.validate_user_can_read.assert_called_once_with(self.mission, self.user)
        self.session.commit.assert_not_awaited()

    async def test_get_by_id_does_not_map_forbidden_mission(self):
        self.validator.validate_user_can_read.side_effect = AccessDeniedError()
        with pytest.raises(AccessDeniedError):
            await self.service.get_mission_by_id(self.mission.id, self.user.id)
        self.mapper.convert_to_dto.assert_not_called()

    async def test_listing_preserves_page_metadata_and_passes_visibility_scope(self):
        request = PageRequest(page=2, size=5)
        filters = MissionFilterDTO(destination='Rome')
        self.repository.find_all.return_value = Page(content=[self.mission], total_elements=12, number=2, size=5)
        with patch('app.services.mission_service_impl.MissionSpecifications.filter_missions') as specification:
            page = await self.service.get_missions(self.user.id, filters, request)
            specification.assert_called_once_with(filters, self.user.id)
            self.repository.find_all.assert_awaited_once_with(specification.return_value, request)
        assert page.content == [self.dto]
        assert (page.total_elements, page.number, page.size, page.total_pages) == (12, 2, 5, 3)

    async def test_admin_listing_has_no_user_visibility_scope(self):
        self.user.is_superuser = True
        self.repository.find_all.return_value = Page(content=[], total_elements=0, number=0, size=20)
        with patch('app.services.mission_service_impl.MissionSpecifications.filter_missions') as specification:
            await self.service.get_missions(self.user.id)
            specification.assert_called_once_with(None, None)

    async def test_specialized_lists_enforce_their_filter_without_mutating_input(self):
        self.repository.find_all.return_value = Page(content=[], total_elements=0, number=0, size=20)
        original = MissionFilterDTO(requester_id=self.manager.id, status=MissionStatus.ACCEPTED, destination='Rome')
        cases = ((self.service.get_sent_missions, 'requester_id', self.user.id), (self.service.get_pending_missions, 'status', MissionStatus.PENDING), (self.service.get_rejected_missions, 'status', MissionStatus.REJECTED))
        for method, field, expected in cases:
            with patch('app.services.mission_service_impl.MissionSpecifications.filter_missions') as specification:
                await method(self.user.id, original)
                selected, user_id = specification.call_args.args
                assert getattr(selected, field) == expected
                assert selected.destination == 'Rome'
                assert user_id == self.user.id
        assert original.requester_id == self.manager.id
        assert original.status == MissionStatus.ACCEPTED

    async def test_create_sets_actor_relationships_status_and_audit(self):
        assert await self.service.create_mission(self.data, self.user.id) is self.dto
        assert self.mission.requester is self.user
        assert self.mission.fund_manager is self.manager
        assert self.mission.status == MissionStatus.PENDING
        assert (self.mission.created_by, self.mission.updated_by) == (self.user.id, self.user.id)
        self.validator.validate_period.assert_called_once_with(self.data.starts_at, self.data.ends_at)
        self.repository.save.assert_awaited_once_with(self.mission)
        self.session.commit.assert_awaited_once()
        self.session.rollback.assert_not_awaited()

    async def test_create_invalid_period_does_not_persist(self):
        self.validator.validate_period.side_effect = InvalidMissionPeriodError()
        with pytest.raises(InvalidMissionPeriodError):
            await self.service.create_mission(self.data, self.user.id)
        self.repository.save.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_create_inactive_actor_stops_before_mapping(self):
        self.users.get_active_user_or_throw.side_effect = AccessDeniedError()
        with pytest.raises(AccessDeniedError):
            await self.service.create_mission(self.data, self.user.id)
        self.mapper.convert_to_entity.assert_not_called()
        self.repository.save.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_update_checks_owner_pending_period_and_assigns_manager(self):
        data = MissionUpdateDTO(**self.data.model_dump())
        created_by = self.mission.created_by
        assert await self.service.update_mission(self.mission.id, data, self.user.id) is self.dto
        self.validator.get_mission_or_throw.assert_awaited_once_with(self.mission.id, for_update=True)
        self.validator.validate_user_is_requester.assert_called_once_with(self.mission, self.user)
        self.validator.validate_mission_is_pending.assert_called_once_with(self.mission)
        self.validator.validate_period.assert_called_once_with(data.starts_at, data.ends_at)
        self.mapper.update_entity.assert_called_once_with(self.mission, data)
        assert self.mission.fund_manager is self.manager
        assert self.mission.updated_by == self.user.id
        assert self.mission.created_by == created_by
        self.session.commit.assert_awaited_once()

    async def test_update_denied_does_not_modify_or_save(self):
        self.validator.validate_user_is_requester.side_effect = AccessDeniedError()
        with pytest.raises(AccessDeniedError):
            await self.service.update_mission(self.mission.id, MissionUpdateDTO(**self.data.model_dump()), self.user.id)
        self.mapper.update_entity.assert_not_called()
        self.repository.save.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_delete_checks_owner_and_state_then_commits(self):
        await self.service.delete_mission(self.mission.id, self.user.id)
        self.validator.get_mission_or_throw.assert_awaited_once_with(self.mission.id, for_update=True)
        self.validator.validate_user_is_requester.assert_called_once_with(self.mission, self.user)
        self.validator.validate_mission_is_pending.assert_called_once_with(self.mission)
        self.repository.delete.assert_awaited_once_with(self.mission)
        self.session.commit.assert_awaited_once()

    async def test_delete_non_pending_mission_does_not_delete(self):
        self.validator.validate_mission_is_pending.side_effect = InvalidMissionStateError()
        with pytest.raises(InvalidMissionStateError):
            await self.service.delete_mission(self.mission.id, self.user.id)
        self.repository.delete.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_accept_updates_state_and_audit_after_manager_check(self):
        assert await self.service.accept_mission(self.mission.id, self.manager.id) is self.dto
        self.validator.validate_user_is_fund_manager.assert_called_once_with(self.mission, self.manager)
        self.validator.validate_mission_is_pending.assert_called_once_with(self.mission)
        self.validator.get_mission_or_throw.assert_awaited_once_with(self.mission.id, for_update=True)
        assert self.mission.status == MissionStatus.ACCEPTED
        assert self.mission.updated_by == self.manager.id
        self.session.commit.assert_awaited_once()

    async def test_reject_updates_state_and_audit(self):
        await self.service.reject_mission(self.mission.id, self.manager.id)
        assert self.mission.status == MissionStatus.REJECTED
        assert self.mission.updated_by == self.manager.id
        self.repository.save.assert_awaited_once_with(self.mission)
        self.session.commit.assert_awaited_once()

    async def test_unauthorized_decision_does_not_change_state(self):
        self.validator.validate_user_is_fund_manager.side_effect = AccessDeniedError()
        with pytest.raises(AccessDeniedError):
            await self.service.accept_mission(self.mission.id, self.user.id)
        assert self.mission.status == MissionStatus.PENDING
        self.repository.save.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_decided_mission_cannot_be_decided_again(self):
        self.mission.status = MissionStatus.ACCEPTED
        self.validator.validate_mission_is_pending.side_effect = InvalidMissionStateError()
        with pytest.raises(InvalidMissionStateError):
            await self.service.reject_mission(self.mission.id, self.manager.id)
        assert self.mission.status == MissionStatus.ACCEPTED
        self.repository.save.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_repository_failure_propagates_and_rolls_back(self):
        failure = RuntimeError('Storage unavailable')
        self.repository.save.side_effect = failure
        with pytest.raises(RuntimeError) as caught:
            await self.service.create_mission(self.data, self.user.id)
        assert caught.value is failure
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_mapping_failure_prevents_commit(self):
        self.mapper.convert_to_dto.side_effect = ValueError('Mapping failed')
        with pytest.raises(ValueError):
            await self.service.create_mission(self.data, self.user.id)
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_commit_failure_propagates_and_rolls_back(self):
        self.session.commit.side_effect = RuntimeError('Commit failed')
        with pytest.raises(RuntimeError):
            await self.service.create_mission(self.data, self.user.id)
        self.session.rollback.assert_awaited_once()
