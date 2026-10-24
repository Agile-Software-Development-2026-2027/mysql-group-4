from decimal import Decimal
from uuid import UUID

from pydantic import ConfigDict, Field, NaiveDatetime

from app.db.enumerated import MissionType
from app.schemas.base import CamelModel


class MissionCreateDTO(CamelModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    mission_type: MissionType
    subject: str = Field(min_length=1, max_length=255)
    destination: str = Field(min_length=1)
    estimated_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    starts_at: NaiveDatetime
    ends_at: NaiveDatetime
    fund_manager_id: UUID
