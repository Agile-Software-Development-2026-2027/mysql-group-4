import pytest

import json
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4
from fastapi import FastAPI, Request
from app.core.exception_handler import access_denied_handler, invalid_mission_handler, register_exception_handlers, resource_not_found_handler, unexpected_error_handler
from app.core.exceptions import AccessDeniedError, InvalidMissionPeriodError, InvalidMissionStateError, MissionNotFoundError, ResourceNotFoundError, UserNotFoundError

class TestExceptionHandler:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self):
        self.request = Request(dict(type='http', method='GET', path='/api/v1/missions/example', query_string=b'token=private', headers=[], scheme='http', server=('test', 80), root_path=''))

    async def test_application_errors_have_expected_status_and_envelope(self):
        cases = ((resource_not_found_handler, MissionNotFoundError(uuid4()), 404), (resource_not_found_handler, UserNotFoundError(uuid4()), 404), (access_denied_handler, AccessDeniedError('Denied'), 403), (invalid_mission_handler, InvalidMissionPeriodError('Invalid period'), 400), (invalid_mission_handler, InvalidMissionStateError('Invalid state'), 400))
        for handler, error, expected in cases:
            response = await handler(self.request, error)
            body = json.loads(response.body)
            assert response.status_code == expected
            assert set(body) == {'timestamp', 'url', 'message'}
            assert body['message'] == str(error)
            assert body['url'] == '/api/v1/missions/example'
            assert datetime.fromisoformat(body['timestamp']).tzinfo is not None

    async def test_unexpected_error_is_logged_without_exposing_details(self):
        error = RuntimeError('private database credentials')
        with patch('app.core.exception_handler.logger') as logger:
            response = await unexpected_error_handler(self.request, error)
        assert response.status_code == 500
        assert json.loads(response.body)['message'] == 'Internal server error'
        assert 'credentials' not in response.body.decode()
        logger.error.assert_called_once()
        assert logger.error.call_args.kwargs['exc_info'][1] is error

    def test_registration_uses_base_not_found_type_and_preserves_fastapi_handlers(self):
        app = FastAPI()
        existing = app.exception_handlers.copy()
        register_exception_handlers(app)
        for exception, handler in existing.items():
            assert app.exception_handlers[exception] is handler
        assert app.exception_handlers[ResourceNotFoundError] is resource_not_found_handler
        assert app.exception_handlers[AccessDeniedError] is access_denied_handler
        assert app.exception_handlers[InvalidMissionStateError] is invalid_mission_handler
        assert app.exception_handlers[InvalidMissionPeriodError] is invalid_mission_handler
        assert app.exception_handlers[Exception] is unexpected_error_handler
