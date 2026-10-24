from uuid import UUID

from sqlalchemy import and_, or_, true
from sqlalchemy.sql.elements import ColumnElement

from app.db.mission import Mission
from app.schemas.mission.frontend2backend import MissionFilterDTO


class MissionSpecifications:
    @staticmethod
    def filter_missions(
        filters: MissionFilterDTO | None = None, user_id: UUID | None = None
    ) -> ColumnElement[bool]:
        conditions: list[ColumnElement[bool]] = []
        if user_id is not None:
            conditions.append(or_(Mission.requester_id == user_id, Mission.fund_manager_id == user_id))
        if filters is None:
            return and_(*conditions) if conditions else true()
        if filters.requester_id is not None:
            conditions.append(Mission.requester_id == filters.requester_id)
        if filters.fund_manager_id is not None:
            conditions.append(Mission.fund_manager_id == filters.fund_manager_id)
        if filters.status is not None:
            conditions.append(Mission.status == filters.status)
        if filters.mission_type is not None:
            conditions.append(Mission.mission_type == filters.mission_type)
        if filters.estimated_cost_min is not None:
            conditions.append(Mission.estimated_cost >= filters.estimated_cost_min)
        if filters.estimated_cost_max is not None:
            conditions.append(Mission.estimated_cost <= filters.estimated_cost_max)
        if filters.starts_at_from is not None:
            conditions.append(Mission.starts_at >= filters.starts_at_from)
        if filters.starts_at_to is not None:
            conditions.append(Mission.starts_at <= filters.starts_at_to)
        if filters.ends_at_from is not None:
            conditions.append(Mission.ends_at >= filters.ends_at_from)
        if filters.ends_at_to is not None:
            conditions.append(Mission.ends_at <= filters.ends_at_to)
        if filters.destination is not None:
            conditions.append(Mission.destination.icontains(filters.destination, autoescape=True))
        return and_(*conditions) if conditions else true()
