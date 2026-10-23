from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import DeclarativeBase

from app.core.enums import EmploymentLevel


class Base(DeclarativeBase):
    pass

class   User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    surname: Mapped[str] = mapped_column(String(50), nullable=False)
    fiscal_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    employment_level: Mapped[EmploymentLevel] = mapped_column(Enum(EmploymentLevel, name="employment_level_enum"), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)