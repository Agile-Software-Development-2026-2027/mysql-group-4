import pytest
from unittest.mock import create_autospec
from pydantic import ValidationError
from app.api import mission_endpoints as controller
from app.core.exceptions import AccessDeniedError
from app.schemas.mission import MissionFilterDTO, MissionUpdateDTO
from app.schemas.page import PageRequest
from app.services.mission_service import MissionService
from tests.factories import make_create_data, make_mission, make_user

class TestMissionController:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self):
        self.user = make_user()
        self.mission_id = make_mission().id
        self.service = create_autospec(MissionService, instance=True)

    @pytest.mark.parametrize('name', ('get_missions', 'get_sent_missions', 'get_pending_missions', 'get_rejected_missions'))
    async def test_all_listing_actions_forward_actor_filters_and_pagination(self, name):
        filters = MissionFilterDTO(destination='Rome')
        page = PageRequest(page=2, size=5)
        operation = getattr(self.service, name)
        result = await getattr(controller, name)(self.user, self.service, page, filters)
        assert result is operation.return_value
        operation.assert_awaited_once_with(self.user.id, filters, page)

    async def test_listing_accepts_no_filters(self):
        await controller.get_missions(self.user, self.service, PageRequest())
        self.service.get_missions.assert_awaited_once_with(self.user.id, None, PageRequest())

    async def test_get_by_id_forwards_authenticated_actor(self):
        result = await controller.get_mission_by_id(self.mission_id, self.user, self.service)
        assert result is self.service.get_mission_by_id.return_value
        self.service.get_mission_by_id.assert_awaited_once_with(self.mission_id, self.user.id)

    async def test_create_forwards_body_and_authenticated_actor(self):
        data = make_create_data()
        result = await controller.create_mission(data, self.user, self.service)
        assert result is self.service.create_mission.return_value
        self.service.create_mission.assert_awaited_once_with(data, self.user.id)

    async def test_update_forwards_id_body_and_authenticated_actor(self):
        data = MissionUpdateDTO(**make_create_data().model_dump())
        result = await controller.update_mission(self.mission_id, data, self.user, self.service)
        assert result is self.service.update_mission.return_value
        self.service.update_mission.assert_awaited_once_with(self.mission_id, data, self.user.id)

    async def test_delete_returns_empty_204_response(self):
        response = await controller.delete_mission(self.mission_id, self.user, self.service)
        assert response.status_code == 204
        assert response.body == b''
        self.service.delete_mission.assert_awaited_once_with(self.mission_id, self.user.id)

    @pytest.mark.parametrize('name', ('accept_mission', 'reject_mission'))
    async def test_decisions_forward_id_and_authenticated_actor(self, name):
        operation = getattr(self.service, name)
        result = await getattr(controller, name)(self.mission_id, self.user, self.service)
        assert result is operation.return_value
        operation.assert_awaited_once_with(self.mission_id, self.user.id)

    async def test_service_exception_propagates_to_global_handler(self):
        self.service.get_mission_by_id.side_effect = AccessDeniedError('Denied')
        with pytest.raises(AccessDeniedError):
            await controller.get_mission_by_id(self.mission_id, self.user, self.service)

class TestPaginationDependency:

    def test_defaults_and_explicit_pagination(self):
        assert controller.get_page_request() == PageRequest(page=0, size=20)
        assert controller.get_page_request(2, 5).offset == 10

    @pytest.mark.parametrize('page,size', ((-1, 20), (0, 0), (0, 101), (True, 20), (0, 1.5)))
    def test_invalid_pagination_is_rejected(self, page, size):
        with pytest.raises(ValidationError):
            controller.get_page_request(page, size)
