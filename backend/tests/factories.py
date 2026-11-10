from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.db import Fund, Mission, User
from app.core.enums import MissionStatus, MissionType
from app.schemas.mission import MissionCreateDTO


def make_user(**overrides):
    return User(**(dict(id=uuid4(), is_active=True, is_superuser=False, hashed_password='x') | overrides))


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
    start = (datetime.now() + timedelta(days=30)).replace(hour=9, minute=0, second=0, microsecond=0)
    return MissionCreateDTO(**(dict(
        mission_type=MissionType.RESEARCH, subject="Research", destination="Rome",
        estimated_cost=Decimal("120.50"), starts_at=start,
        ends_at=start + timedelta(days=2, hours=9), fund_manager_id=uuid4(),
    ) | overrides))


def make_fund(**overrides):
    return Fund(**(dict(
        id=uuid4(), name="Research fund", description="Lab equipment", amount=Decimal("5000.00"),
        responsible_fc="RSSMRA80A01H501U",
        created_at=datetime(2026, 10, 24), updated_at=datetime(2026, 10, 24),
        created_by=uuid4(), updated_by=uuid4(),
    ) | overrides))
