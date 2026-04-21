from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.db.types import UUIDPK


class City(Base, TimestampMixin):
    """Cidade atendida pela plataforma ISV Delivery.

    Referenciada por stores, addresses e orders.
    Usa is_active em vez de deleted_at (ver ADR-008).
    """

    __tablename__ = "cities"

    id: Mapped[UUIDPK]
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    def __repr__(self) -> str:
        return f"<City {self.slug} ({self.state})>"
