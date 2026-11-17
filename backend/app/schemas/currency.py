from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CurrencyConversionDTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    original_currency: str
    original_amount: Decimal
    converted_amount: Decimal
    rate: Decimal
    date: str
    provider: str


class MissionCurrencyProfileDTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    destination: str | None = None
    default_currency: str = "EUR"

