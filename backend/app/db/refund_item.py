import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ExpenseCategory, ExpenseSubtype
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.refund_request import RefundRequest


class RefundItem(Base):
    __tablename__ = "refund_items"
    __table_args__ = (
        CheckConstraint(
            "requested_amount > 0 AND requested_amount <= 10000.00",
            name="ck_refund_items_requested_amount_range",
        ),
        CheckConstraint(
            "reimbursed_amount IS NULL OR (reimbursed_amount >= 0 AND reimbursed_amount <= requested_amount)",
            name="ck_refund_items_reimbursed_range",
        ),
        CheckConstraint(
            """
            (category = 'TRANSPORT' AND itinerary_from IS NOT NULL AND itinerary_to IS NOT NULL AND ends_at IS NOT NULL)
            OR
            (category != 'TRANSPORT' AND itinerary_from IS NULL AND itinerary_to IS NULL)
            """,
            name="ck_refund_items_transport_itinerary",
        ),
        CheckConstraint(
            "(category NOT IN ('MEALS', 'OTHER')) OR (ends_at IS NULL)",
            name="ck_refund_items_meals_other_no_ends_at",
        ),
        CheckConstraint(
            "(category != 'ACCOMMODATION') OR (ends_at IS NOT NULL AND ends_at >= starts_at)",
            name="ck_refund_items_accommodation_dates",
        ),
        CheckConstraint(
            "(category = 'OTHER' AND subtype IS NULL) OR (category != 'OTHER' AND subtype IS NOT NULL)",
            name="ck_refund_items_other_no_subtype",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4
    )
    refund_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("refund_requests.id", name="fk_refund_items_refund_request", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory, name="expense_category", validate_strings=True),
        nullable=False,
        index=True,
    )
    subtype: Mapped[ExpenseSubtype | None] = mapped_column(
        Enum(ExpenseSubtype, name="expense_subtype", validate_strings=True),
        nullable=True,
    )

    itinerary_from: Mapped[str | None] = mapped_column(String(255), nullable=True)
    itinerary_to: Mapped[str | None] = mapped_column(String(255), nullable=True)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reimbursed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="EUR", server_default=text("'EUR'")
    )
    is_traceable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    receipt_file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    receipt_original_filename: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    refund_request: Mapped["RefundRequest"] = relationship(
        back_populates="items",
        lazy="raise",
    )
