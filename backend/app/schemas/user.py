import uuid
from pydantic import ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from fastapi_users import schemas

FISCAL_CODE_REGEX = r"^[A-Za-z]{6}[0-9]{2}[A-Za-z][0-9]{2}[A-Za-z][0-9]{3}[A-Za-z]$"

class UserRead(schemas.BaseUser[uuid.UUID]):
    name: str
    surname: str
    fiscal_code: str

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class UserCreate(schemas.BaseUserCreate):
    name: str = Field(...,min_length=2, max_length=50,description="",)
    surname: str = Field(..., min_length=2, max_length=50,description="Cognome dell'utente (tra 2 e 50 caratteri)",)
    fiscal_code: str = Field( ..., min_length=16, max_length=16, pattern=FISCAL_CODE_REGEX, description="Codice Fiscale italiano (esattamente 16 caratteri alfanumerici)")
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    @field_validator("fiscal_code")
    @classmethod
    def normalize_fiscal_code(cls, v: str) -> str:
        return v.strip().upper() if v else v
