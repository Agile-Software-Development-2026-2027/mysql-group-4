from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.enums import ExpenseCategory, ExpenseSubtype


class ReceiptAutocompleteDTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    category: ExpenseCategory | None = None
    subtype: ExpenseSubtype | None = None
    amount: Decimal | None = None
    currency: str | None = None
    converted_amount_eur: Decimal | None = None
    exchange_rate: Decimal | None = None
    rate_date: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    merchant: str | None = None
    description: str | None = None
    itinerary_from: str | None = None
    itinerary_to: str | None = None
    raw_text: str = ""
    confidence: float | None = None
    ocr_engine: str = ""
    llm_model: str = ""
    warnings: list[str] = Field(default_factory=list)


class BoundingBoxDTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    page: int = Field(default=0, ge=0)


class ReceiptPageDTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    page: int = Field(ge=0)
    image_width: int
    image_height: int
    image_data_url: str


class ReceiptDetectionResponseDTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    image_width: int
    image_height: int
    boxes: list[BoundingBoxDTO] = Field(default_factory=list)
    pages: list[ReceiptPageDTO] = Field(default_factory=list)