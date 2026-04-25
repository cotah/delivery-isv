from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.db.types import UUIDPK


class Category(Base, TimestampMixin):
    """Categoria de Store (tabela lookup, ADR-013).

    Valores configuráveis pelo admin: pizzaria, lanchonete, marmita,
    etc. Novas categorias podem ser adicionadas sem deploy.

    Sem soft delete — controle de disponibilidade via is_active.
    Pattern consistente com cities (ADR-008).

    display_order: posição em listagens (admin define ordem visual).
    Migration popula sequencialmente por created_at em rows existentes.
    Default 0 em novas rows — admin organiza depois.
    """

    __tablename__ = "categories"

    id: Mapped[UUIDPK]
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    def __repr__(self) -> str:
        return f"<Category {self.slug} order={self.display_order}>"
