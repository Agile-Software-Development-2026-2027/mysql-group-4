from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, NaiveDatetime, model_validator

from app.schemas.base import CamelModel
from app.db.enumerated.mission_status import MissionStatus
from app.db.enumerated.mission_type import MissionType


class MissionFilterDTO(CamelModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    requester_id: UUID | None = None
    fund_manager_id: UUID | None = None
    status: MissionStatus | None = None
    mission_type: MissionType | None = None
    estimated_cost_min: Decimal | None = Field(default=None, ge=0)
    estimated_cost_max: Decimal | None = Field(default=None, ge=0)
    starts_at_from: NaiveDatetime | None = None
    starts_at_to: NaiveDatetime | None = None
    ends_at_from: NaiveDatetime | None = None
    ends_at_to: NaiveDatetime | None = None
    destination: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        ranges = (
            ("estimated_cost", self.estimated_cost_min, self.estimated_cost_max),
            ("starts_at", self.starts_at_from, self.starts_at_to),
            ("ends_at", self.ends_at_from, self.ends_at_to),
        )
        for name, lower, upper in ranges:
            if lower is not None and upper is not None and lower > upper:
                raise ValueError(f"Invalid {name} range: lower bound exceeds upper bound")
        return self
