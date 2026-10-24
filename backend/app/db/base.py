from sqlalchemy.orm import DeclarativeBase

from app.db.auditable_entity import AuditableEntity


class Base(AuditableEntity, DeclarativeBase):
    pass
