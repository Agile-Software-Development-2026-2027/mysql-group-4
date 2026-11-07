import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import RefundStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.mission import Mission
    from app.db.refund_item import RefundItem


class RefundRequest(Base):
    __tablename__ = "refund_requests"
    __table_args__ = (
        CheckConstraint(
            "total_requested_amount >= 0",
            name="ck_refund_requests_total_requested_nonnegative",
        ),
        CheckConstraint(
            "total_reimbursed_amount >= 0",
            name="ck_refund_requests_total_reimbursed_nonnegative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("missions.id", name="fk_refund_requests_mission", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status", validate_strings=True),
        nullable=False,
        default=RefundStatus.DRAFT,
        server_default=text("'DRAFT'"),
        index=True,
    )
    total_requested_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    total_reimbursed_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    mission: Mapped["Mission"] = relationship(
        back_populates="refund_request",
        lazy="raise",
    )

    items: Mapped[list["RefundItem"]] = relationship(
        back_populates="refund_request",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
