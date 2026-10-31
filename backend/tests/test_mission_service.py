import pytest
from unittest.mock import create_autospec, patch
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
from app.schemas.mission import MissionDTO, MissionFilterDTO, MissionUpdateDTO
from app.schemas.page import Page, PageRequest
from app.services.mission_service import MissionService
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
        self.user_repository = create_autospec(UserRepository, instance=True)
        self.user_repository.get_user_by_id.side_effect = lambda session, user_id: {
            self.user.id: self.user,
            self.manager.id: self.manager,
        }.get(user_id)
        self.repository.find_by_id.return_value = self.mission
        self.repository.find_by_id_for_update.return_value = self.mission

        def fake_save(m):
            if m.id is None:
                m.id = self.mission.id
            if m.requester_id is None and m.requester:
                m.requester_id = m.requester.id
            if getattr(m, "created_at", None) is None:
                m.created_at = self.mission.created_at
            if getattr(m, "updated_at", None) is None:
                m.updated_at = self.mission.updated_at
            return m

        self.repository.save.side_effect = fake_save
        self.dto = MissionDTO.model_validate(self.mission)
        self.service = MissionService(self.session, self.repository, self.user_repository)

    async def test_get_by_id_checks_visibility_before_mapping(self):
        result = await self.service.get_mission_by_id(self.mission.id, self.user.id)
        assert result == self.dto
        self.repository.find_by_id.assert_awaited_once_with(self.mission.id)
        self.session.commit.assert_not_awaited()

    async def test_get_by_id_does_not_map_forbidden_mission(self):
        other_user = make_user()
        self.user_repository.get_user_by_id.side_effect = lambda session, user_id: other_user
        with pytest.raises(AccessDeniedError):
            await self.service.get_mission_by_id(self.mission.id, other_user.id)

    async def test_get_by_id_missing_mission_raises_not_found(self):
        self.repository.find_by_id.return_value = None
        with pytest.raises(MissionNotFoundError):
            await self.service.get_mission_by_id(self.mission.id, self.user.id)

    async def test_listing_preserves_page_metadata_and_passes_visibility_scope(self):
        request = PageRequest(page=2, size=5)
        filters = MissionFilterDTO(destination="Rome")
        self.repository.find_all.return_value = Page(content=[self.mission], total_elements=12, number=2, size=5)
        page = await self.service.get_missions(self.user.id, filters, request)
        self.repository.find_all.assert_awaited_once_with(
            filters=filters,
            user_id=self.user.id,
            page_request=request,
        )
        assert page.content == [self.dto]
        assert (page.total_elements, page.number, page.size, page.total_pages) == (12, 2, 5, 3)

    async def test_admin_listing_has_no_user_visibility_scope(self):
        self.user.is_superuser = True
        self.repository.find_all.return_value = Page(content=[], total_elements=0, number=0, size=20)
        await self.service.get_missions(self.user.id)
        self.repository.find_all.assert_awaited_once_with(
            filters=None,
            user_id=None,
            page_request=None,
        )

    async def test_specialized_lists_enforce_their_filter_without_mutating_input(self):
        self.repository.find_all.return_value = Page(content=[], total_elements=0, number=0, size=20)
        original = MissionFilterDTO(requester_id=self.manager.id, status=MissionStatus.ACCEPTED, destination="Rome")
        cases = (
            (self.service.get_sent_missions, "requester_id", self.user.id),
            (self.service.get_pending_missions, "status", MissionStatus.PENDING),
            (self.service.get_rejected_missions, "status", MissionStatus.REJECTED),
        )
        for method, field, expected in cases:
            self.repository.find_all.reset_mock()
            await method(self.user.id, original)
            self.repository.find_all.assert_awaited_once()
            called_filters = self.repository.find_all.call_args.kwargs["filters"]
            called_user_id = self.repository.find_all.call_args.kwargs["user_id"]
            assert getattr(called_filters, field) == expected
            assert called_filters.destination == "Rome"
            assert called_user_id == self.user.id
        assert original.requester_id == self.manager.id
        assert original.status == MissionStatus.ACCEPTED

    async def test_missions_to_approve_enforce_fund_manager_and_pending(self):
        self.repository.find_all.return_value = Page(content=[], total_elements=0, number=0, size=20)
        original = MissionFilterDTO(
            fund_manager_id=self.user.id, status=MissionStatus.ACCEPTED, destination="Rome")
        await self.service.get_missions_to_approve(self.manager.id, original)
        called_filters = self.repository.find_all.call_args.kwargs["filters"]
        assert called_filters.fund_manager_id == self.manager.id
        assert called_filters.status == MissionStatus.PENDING
        assert called_filters.destination == "Rome"
        assert self.repository.find_all.call_args.kwargs["user_id"] == self.manager.id
        assert original.fund_manager_id == self.user.id
        assert original.status == MissionStatus.ACCEPTED

    async def test_missions_to_approve_returns_mapped_page(self):
        self.repository.find_all.return_value = Page(content=[self.mission], total_elements=1, number=0, size=20)
        page = await self.service.get_missions_to_approve(self.manager.id)
        assert page.content == [self.dto]
        assert page.total_elements == 1

    async def test_missions_to_approve_unknown_user_raises_not_found(self):
        with pytest.raises(UserNotFoundError):
            await self.service.get_missions_to_approve(make_user().id)
        self.repository.find_all.assert_not_awaited()

    async def test_create_sets_actor_relationships_status_and_audit(self):
        result = await self.service.create_mission(self.data, self.user.id)
        saved_mission = self.repository.save.call_args[0][0]
        assert saved_mission.requester is self.user
        assert saved_mission.fund_manager is self.manager
        assert saved_mission.status == MissionStatus.PENDING
        assert (saved_mission.created_by, saved_mission.updated_by) == (self.user.id, self.user.id)
        assert result.subject == self.data.subject
        self.session.commit.assert_awaited_once()
        self.session.rollback.assert_not_awaited()

    async def test_create_inactive_actor_stops_before_mapping(self):
        self.user.is_active = False
        with pytest.raises(AccessDeniedError):
            await self.service.create_mission(self.data, self.user.id)
        self.repository.save.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_update_allowed_for_admin_and_assigns_manager(self):
        admin = make_user(is_superuser=True)
        self.user_repository.get_user_by_id.side_effect = lambda session, user_id: {
            admin.id: admin,
            self.manager.id: self.manager,
        }.get(user_id)
        data = MissionUpdateDTO(**self.data.model_dump())
        created_by = self.mission.created_by
        result = await self.service.update_mission(self.mission.id, data, admin.id)
        self.repository.find_by_id_for_update.assert_awaited_once_with(self.mission.id)
        assert self.mission.subject == data.subject
        assert self.mission.fund_manager is self.manager
        assert self.mission.updated_by == admin.id
        assert self.mission.created_by == created_by
        assert result.id == self.mission.id
        self.session.commit.assert_awaited_once()

    async def test_update_denied_for_regular_user(self):
        self.user.is_superuser = False
        data = MissionUpdateDTO(**self.data.model_dump())
        with pytest.raises(AccessDeniedError):
            await self.service.update_mission(self.mission.id, data, self.user.id)
        self.repository.save.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_delete_checks_owner_and_state_then_commits(self):
        await self.service.delete_mission(self.mission.id, self.user.id)
        self.repository.find_by_id_for_update.assert_awaited_once_with(self.mission.id)
        self.repository.delete.assert_awaited_once_with(self.mission)
        self.session.commit.assert_awaited_once()

    async def test_delete_denied_for_non_requester(self):
        with pytest.raises(AccessDeniedError):
            await self.service.delete_mission(self.mission.id, self.manager.id)
        self.repository.delete.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_delete_non_pending_mission_does_not_delete(self):
        self.mission.status = MissionStatus.ACCEPTED
        with pytest.raises(InvalidMissionStateError):
            await self.service.delete_mission(self.mission.id, self.user.id)
        self.repository.delete.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_accept_updates_state_and_audit_after_manager_check(self):
        result = await self.service.accept_mission(self.mission.id, self.manager.id, "Approvo")
        self.repository.find_by_id_for_update.assert_awaited_once_with(self.mission.id)
        assert self.mission.status == MissionStatus.ACCEPTED
        assert self.mission.response == "Approvo"
        assert self.mission.updated_by == self.manager.id
        assert result.status == MissionStatus.ACCEPTED
        self.session.commit.assert_awaited_once()

    async def test_reject_updates_state_and_audit(self):
        await self.service.reject_mission(self.mission.id, self.manager.id, "Rifiuto")
        assert self.mission.status == MissionStatus.REJECTED
        assert self.mission.response == "Rifiuto"
        assert self.mission.updated_by == self.manager.id
        self.repository.save.assert_awaited_once_with(self.mission)
        self.session.commit.assert_awaited_once()

    async def test_unauthorized_decision_does_not_change_state(self):
        with pytest.raises(AccessDeniedError):
            await self.service.accept_mission(self.mission.id, self.user.id, "Approvo")
        assert self.mission.status == MissionStatus.PENDING
        self.repository.save.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_decided_mission_cannot_be_decided_again(self):
        self.mission.status = MissionStatus.ACCEPTED
        with pytest.raises(InvalidMissionStateError):
            await self.service.reject_mission(self.mission.id, self.manager.id, "Rifiuto")
        assert self.mission.status == MissionStatus.ACCEPTED
        self.repository.save.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_repository_failure_propagates_and_rolls_back(self):
        failure = RuntimeError("Storage unavailable")
        self.repository.save.side_effect = failure
        with pytest.raises(RuntimeError) as caught:
            await self.service.create_mission(self.data, self.user.id)
        assert caught.value is failure
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_mapping_failure_prevents_commit(self):
        with patch("app.services.mission_service.MissionDTO.model_validate", side_effect=ValueError("Mapping failed")):
            with pytest.raises(ValueError):
                await self.service.create_mission(self.data, self.user.id)
        self.session.commit.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_commit_failure_propagates_and_rolls_back(self):
        self.session.commit.side_effect = RuntimeError("Commit failed")
        with pytest.raises(RuntimeError):
            await self.service.create_mission(self.data, self.user.id)
        self.session.rollback.assert_awaited_once()