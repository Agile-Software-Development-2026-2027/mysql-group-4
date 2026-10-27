from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.page import Page, PageRequest

T = TypeVar("T")


async def paginate(
    session: AsyncSession,
    query: Select[tuple[T]],
    page: int = 0,
    size: int = 20,
) -> Page[T]:
    pagination = PageRequest(page=page, size=size)
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = await session.scalar(count_query)
    result = await session.scalars(query.offset(pagination.offset).limit(pagination.size))
    return Page(
        content=list(result.all()),
        total_elements=total if total is not None else 0,
        number=pagination.page,
        size=pagination.size,
    )
