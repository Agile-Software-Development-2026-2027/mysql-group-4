import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.db.models import User


class Fund(Base):
    __tablename__ = "funds"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_funds_amount_nonnegative"),
        CheckConstraint("length(name) BETWEEN 1 AND 100", name="ck_funds_name_length"),
        CheckConstraint("committed_amount >= 0", name="ck_funds_committed_amount_nonnegative"),
        CheckConstraint("amount >= committed_amount", name="ck_funds_amount_geq_committed_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    committed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal('0.0'))
    responsible_fc: Mapped[str] = mapped_column(
        ForeignKey(
            "users.fiscal_code",
            name="funds_responsible",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    responsible: Mapped["User"] = relationship(
        back_populates="funds",
        foreign_keys=[responsible_fc],
        cascade="save-update, merge",
        lazy="raise",
    )
