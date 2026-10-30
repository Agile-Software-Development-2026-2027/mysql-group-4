import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.enums import MissionStatus, MissionType



if TYPE_CHECKING:
    from app.db.models import User
    from app.db.mission_document import MissionDocument


class Mission(Base):
    __tablename__ = "missions"
    __table_args__ = (
        CheckConstraint("estimated_cost >= 0", name="ck_missions_estimated_cost_nonnegative"),
        CheckConstraint("length(subject) BETWEEN 1 AND 255", name="ck_missions_subject_length"),
        CheckConstraint("length(destination) >= 1", name="ck_missions_destination_nonempty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4
    )
    mission_type: Mapped[MissionType] = mapped_column(
        Enum(MissionType, name="mission_type", validate_strings=True), nullable=False
    )
    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus, name="mission_status", validate_strings=True),
        nullable=False,
        default=MissionStatus.PENDING,
        server_default=text("'PENDING'"),
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="missions_requester", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fund_manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="missions_fund_manager", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    requester: Mapped["User"] = relationship(
        back_populates="requested_missions",
        foreign_keys=[requester_id],
        cascade="save-update, merge",
        lazy="raise",
    )

    fund_manager: Mapped["User"] = relationship(
        back_populates="funded_missions",
        foreign_keys=[fund_manager_id],
        cascade="save-update, merge",
        lazy="raise",
    )

    documents: Mapped[list["MissionDocument"]] = relationship(
        back_populates="mission",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )