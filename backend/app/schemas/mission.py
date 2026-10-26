from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, NaiveDatetime, model_validator

from app.db.enumerated.mission_status import MissionStatus
from app.db.enumerated.mission_type import MissionType
from app.schemas.base import CamelModel


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


class MissionCreateDTO(CamelModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    mission_type: MissionType
    subject: str = Field(min_length=1, max_length=255)
    destination: str = Field(min_length=1)
    estimated_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    starts_at: NaiveDatetime
    ends_at: NaiveDatetime
    fund_manager_id: UUID


class MissionUpdateDTO(MissionCreateDTO):
    pass


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
