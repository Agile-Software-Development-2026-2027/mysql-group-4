from sqlalchemy.ext.asyncio import AsyncSession


class RefundRepository:
    async def create_fund_request(self, session: AsyncSession):
        pass


refund_repository = RefundRepository()