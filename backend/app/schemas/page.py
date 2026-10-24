from collections.abc import Callable
from typing import Generic, TypeVar

from pydantic import ConfigDict, Field, computed_field

from app.schemas.base import CamelModel

T = TypeVar("T")
R = TypeVar("R")


class PageRequest(CamelModel):
    model_config = ConfigDict(frozen=True)

    page: int = Field(default=0, ge=0, strict=True)
    size: int = Field(default=20, ge=1, le=100, strict=True)

    @property
    def offset(self) -> int:
        return self.page * self.size


class Page(CamelModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    content: list[T]
    total_elements: int = Field(ge=0)
    number: int = Field(ge=0)
    size: int = Field(ge=1, le=100)

    def map(self, converter: Callable[[T], R]) -> "Page[R]":
        return Page(
            content=[converter(item) for item in self.content],
            total_elements=self.total_elements,
            number=self.number,
            size=self.size,
        )

    @computed_field
    @property
    def total_pages(self) -> int:
        return (self.total_elements + self.size - 1) // self.size

    @computed_field
    @property
    def number_of_elements(self) -> int:
        return len(self.content)

    @computed_field
    @property
    def first(self) -> bool:
        return self.number == 0

    @computed_field
    @property
    def last(self) -> bool:
        return self.number + 1 >= self.total_pages

    @computed_field
    @property
    def empty(self) -> bool:
        return not self.content
