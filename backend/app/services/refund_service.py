from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.mission_repository import MissionRepository
from app.crud.refund_repository import RefundRepository


class RefundService:
    def __init__(self, session: AsyncSession, refund_repository: RefundRepository, mission_repository: MissionRepository):
        self.session = session
        self.refund_repository = refund_repository
        self.mission_repository = mission_repository