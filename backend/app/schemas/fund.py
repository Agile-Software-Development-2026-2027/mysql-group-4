from decimal import Decimal
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.base import CamelModel


class FundDTO(CamelModel):
    id: UUID
    name: str
    description: str | None = None
    amount: Decimal
    responsible_fc: str
    locked_by_mission_id: UUID | None = None
    mission_subject: str | None = None
    requested_amount: Decimal | None = None
    requester_name: str | None = None


class FundCreateDTO(CamelModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class FundUpdateDTO(FundCreateDTO):
    pass
