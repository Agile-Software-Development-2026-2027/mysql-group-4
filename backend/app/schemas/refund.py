from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, NaiveDatetime, model_validator

from app.core.enums import ExpenseCategory, ExpenseSubtype, RefundStatus
from app.schemas.base import CamelModel


MAX_EXPENSE_AMOUNT = Decimal("10000.00")

TRANSPORT_SUBTYPES = {
    ExpenseSubtype.TRAIN, ExpenseSubtype.PLANE, ExpenseSubtype.SHIP,
    ExpenseSubtype.PUBLIC_TRANSPORT, ExpenseSubtype.TAXI_RENTAL, ExpenseSubtype.OWN_VEHICLE
}
ACCOMMODATION_SUBTYPES = {
    ExpenseSubtype.ACCOMMODATION_EXPENSE, ExpenseSubtype.OTHER_ACCOMMODATION_EXPENSE
}
MEALS_SUBTYPES = {
    ExpenseSubtype.MEALS_EXPENSE, ExpenseSubtype.OTHER_MEALS_EXPENSE
}


class RefundItemBase(CamelModel):
    category: ExpenseCategory
    subtype: ExpenseSubtype | None = None
    itinerary_from: str | None = Field(default=None, min_length=1, max_length=255)
    itinerary_to: str | None = Field(default=None, min_length=1, max_length=255)
    starts_at: NaiveDatetime
    ends_at: NaiveDatetime | None = None
    requested_amount: Decimal = Field(gt=0, le=MAX_EXPENSE_AMOUNT, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    is_traceable: bool = True
    description: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_category_rules(self) -> Self:
        if self.category == ExpenseCategory.OTHER:
            if self.subtype is not None:
                raise ValueError("Subtype is not allowed for OTHER expenses")
            if self.itinerary_from is not None or self.itinerary_to is not None:
                raise ValueError("Itinerary is not allowed for OTHER expenses")
            if self.ends_at is not None:
                raise ValueError("End time (ends_at) is not allowed for OTHER expenses")

        elif self.category == ExpenseCategory.TRANSPORT:
            if self.subtype not in TRANSPORT_SUBTYPES:
                raise ValueError("Valid transport subtype is required")
            if not self.itinerary_from or not self.itinerary_to:
                raise ValueError("Itinerary (itinerary_from and itinerary_to) is required for transport expenses")
            if self.ends_at is None:
                raise ValueError("Arrival time (ends_at) is required for transport expenses")
            if self.ends_at < self.starts_at:
                raise ValueError("Arrival time must be after departure time")

        elif self.category == ExpenseCategory.ACCOMMODATION:
            if self.subtype not in ACCOMMODATION_SUBTYPES:
                raise ValueError("Valid accommodation subtype is required")
            if self.itinerary_from is not None or self.itinerary_to is not None:
                raise ValueError("Itinerary is not allowed for accommodation expenses")
            if self.ends_at is None:
                raise ValueError("Check-out time (ends_at) is required for accommodation expenses")
            if self.ends_at < self.starts_at:
                raise ValueError("Check-out time must be after check-in time")

        elif self.category == ExpenseCategory.MEALS:
            if self.subtype not in MEALS_SUBTYPES:
                raise ValueError("Valid meals subtype is required")
            if self.itinerary_from is not None or self.itinerary_to is not None:
                raise ValueError("Itinerary is not allowed for MEALS expenses")
            if self.ends_at is not None:
                raise ValueError("End time (ends_at) is not allowed for MEALS expenses")

        return self


class RefundItemCreateDTO(RefundItemBase):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class RefundItemDTO(RefundItemBase):
    id: UUID
    refund_request_id: UUID
    reimbursed_amount: Decimal | None = None
    receipt_file_path: str
    receipt_original_filename: str
    admin_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    updated_by: UUID | None = None


class RefundRequestCreateDTO(CamelModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    mission_id: UUID


class RefundRequestDTO(CamelModel):
    id: UUID
    mission_id: UUID
    status: RefundStatus
    total_requested_amount: Decimal
    total_reimbursed_amount: Decimal
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    updated_by: UUID | None = None
    items: list[RefundItemDTO] = Field(default_factory=list)


class RefundRequesterDTO(CamelModel):
    id: UUID
    name: str
    surname: str
    department: str


class RefundMissionDTO(CamelModel):
    id: UUID
    subject: str
    destination: str
    starts_at: datetime
    ends_at: datetime
    estimated_cost: Decimal
    requester: RefundRequesterDTO


class RefundReviewDTO(RefundRequestDTO):
    mission: RefundMissionDTO