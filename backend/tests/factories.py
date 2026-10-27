from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.db import Mission, User
from app.db.enumerated import MissionStatus, MissionType
from app.schemas.mission import MissionCreateDTO


def make_user(**overrides):
    return User(**(dict(id=uuid4(), is_active=True, is_superuser=False) | overrides))


def make_mission(**overrides):
    return Mission(**(dict(
        id=uuid4(), mission_type=MissionType.RESEARCH, status=MissionStatus.PENDING,
        subject="Research", destination="Rome", estimated_cost=Decimal("120.50"),
        starts_at=datetime(2026, 11, 1, 9), ends_at=datetime(2026, 11, 3, 18),
        requester_id=uuid4(), fund_manager_id=uuid4(),
        created_at=datetime(2026, 10, 24), updated_at=datetime(2026, 10, 24),
        created_by=uuid4(), updated_by=uuid4(),
    ) | overrides))


def make_create_data(**overrides):
    return MissionCreateDTO(**(dict(
        mission_type=MissionType.RESEARCH, subject="Research", destination="Rome",
        estimated_cost=Decimal("120.50"), starts_at=datetime(2026, 11, 1, 9),
        ends_at=datetime(2026, 11, 3, 18), fund_manager_id=uuid4(),
    ) | overrides))
