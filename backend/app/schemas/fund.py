from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import ConfigDict, Field, computed_field

from app.core.enums import MissionStatus
from app.schemas.base import CamelModel


class FundMissionDTO(CamelModel):
    id: UUID
    subject: str
    status: MissionStatus
    estimated_cost: Decimal
    requester_name: str
    requested_at: datetime


class FundDTO(CamelModel):
    id: UUID
    name: str
    description: str | None = None
    amount: Decimal
    committed_amount: Decimal
    responsible_fc: str
    missions: list[FundMissionDTO] = []

    @computed_field
    @property
    def remaining_amount(self) -> Decimal:
        return self.amount - self.committed_amount


class FundCreateDTO(CamelModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class FundUpdateDTO(FundCreateDTO):
    pass
