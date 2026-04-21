from sqlalchemy import Boolean, String
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

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"
