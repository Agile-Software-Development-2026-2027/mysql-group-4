from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.schemas.base import CamelModel
from app.db.enumerated.mission_status import MissionStatus
from app.db.enumerated.mission_type import MissionType


class MissionDTO(CamelModel):
    id: UUID
    mission_type: MissionType
    status: MissionStatus
    subject: str
    destination: str
    estimated_cost: Decimal
    starts_at: datetime
    ends_at: datetime
    requester_id: UUID
    fund_manager_id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None
