import pytest

from datetime import timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from pydantic import ValidationError
from app.db.mission import Mission
from app.schemas.mission import MissionCreateDTO, MissionDTO, MissionFilterDTO, MissionUpdateDTO
from app.schemas.page import Page
from tests.factories import make_create_data, make_mission

class TestMissionDTO:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self):
        self.values = make_create_data().model_dump()

    def test_camel_case_input_and_whitespace_normalization(self):
        payload = make_create_data().model_dump(mode='json', by_alias=True)
        payload['subject'] = '  Research  '
        dto = MissionCreateDTO.model_validate(payload)
        assert dto.subject == 'Research'
        assert dto.estimated_cost == Decimal('120.50')

    def test_invalid_create_fields_are_rejected(self):
        cases = ({'subject': '   '}, {'subject': 'x' * 256}, {'destination': ''}, {'estimated_cost': '-0.01'}, {'estimated_cost': '1.001'}, {'estimated_cost': '10000000000.00'}, {'fund_manager_id': 'invalid'}, {'starts_at': self.values['starts_at'].replace(tzinfo=timezone.utc)}, {'ends_at': self.values['starts_at']})
        for changes in cases:
            with pytest.raises(ValidationError):
                MissionCreateDTO(**self.values | changes)

    def test_client_cannot_supply_identity_state_or_audit(self):
        for field in ('id', 'requester_id', 'status', 'created_by', 'updated_by', 'created_at', 'updated_at', 'response'):
            with pytest.raises(ValidationError):
                MissionCreateDTO(**self.values | {field: str(uuid4())})

    def test_update_requires_complete_body(self):
        with pytest.raises(ValidationError):
            MissionUpdateDTO(subject='New subject')

    def test_all_filters_are_optional(self):
        assert all((value is None for value in MissionFilterDTO().model_dump().values()))

    def test_inverted_filter_ranges_are_rejected(self):
        start = self.values['starts_at']
        for values in (dict(estimated_cost_min=20, estimated_cost_max=10), dict(starts_at_from=start, starts_at_to=start - timedelta(days=1)), dict(ends_at_from=start, ends_at_to=start - timedelta(days=1))):
            with pytest.raises(ValidationError):
                MissionFilterDTO(**values)

    def test_equal_and_single_sided_filter_bounds_are_allowed(self):
        assert MissionFilterDTO(estimated_cost_min=10, estimated_cost_max=10).estimated_cost_min == 10
        assert MissionFilterDTO(estimated_cost_max=0).estimated_cost_max == 0

class TestMissionModelIntegration:

    def test_entity_to_dto_uses_relationship_ids_and_camel_case(self):
        mission = make_mission()
        dto = MissionDTO.model_validate(mission)
        payload = dto.model_dump(mode='json', by_alias=True)
        assert payload['requesterId'] == str(mission.requester_id)
        assert payload['fundManagerId'] == str(mission.fund_manager_id)
        assert 'requester' not in payload
        assert 'fundManager' not in payload
        assert set(dto.model_dump()) == set(mission.__table__.columns.keys())

    def test_creation_maps_editable_fields(self):
        data = make_create_data()
        mission = Mission(**data.model_dump())
        for field, value in data.model_dump().items():
            assert getattr(mission, field) == value
        assert mission.id is None
        assert mission.requester_id is None

    def test_update_preserves_identity_requester_state_and_audit(self):
        mission = make_mission()
        protected = {field: getattr(mission, field) for field in ('id', 'requester_id', 'status', 'created_by', 'created_at', 'updated_by', 'updated_at', 'response')}
        data = MissionUpdateDTO(**make_create_data(subject='Updated', destination='Paris').model_dump())
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(mission, field, value)
        for field, value in data.model_dump().items():
            assert getattr(mission, field) == value
        assert protected == {field: getattr(mission, field) for field in protected}

class TestPage:

    def test_mapping_preserves_totals_and_page_boundaries(self):
        source = Page[int](content=[1, 2], total_elements=12, number=2, size=5)
        mapped = source.map(str)
        assert mapped.content == ['1', '2']
        assert source.content == [1, 2]
        assert (mapped.total_elements, mapped.number, mapped.size) == (12, 2, 5)
        assert mapped.total_pages == 3
        assert mapped.number_of_elements == 2
        assert mapped.last
        assert not mapped.first

    def test_empty_page_metadata(self):
        page = Page(content=[], total_elements=0, number=0, size=20)
        assert page.empty and page.first and page.last
        assert page.total_pages == 0
        assert page.model_dump(by_alias=True)['numberOfElements'] == 0