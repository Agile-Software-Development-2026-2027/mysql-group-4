from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.mission import Mission

class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    surname: Mapped[str] = mapped_column(String(50), nullable=False)
    fiscal_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)

    requested_missions: Mapped[list["Mission"]] = relationship(
        back_populates="requester",
        foreign_keys="Mission.requester_id",
        lazy="raise",
        passive_deletes="all",
    )
    funded_missions: Mapped[list["Mission"]] = relationship(
        back_populates="fund_manager",
        foreign_keys="Mission.fund_manager_id",
        lazy="raise",
        passive_deletes="all",
    )
