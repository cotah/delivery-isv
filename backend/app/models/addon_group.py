from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.domain.enums import AddonGroupType

# CHECK constraint gerada do enum (ADR-006)
_ADDON_GROUP_TYPE_CHECK = "type IN (" + ", ".join(f"'{t.value}'" for t in AddonGroupType) + ")"


class AddonGroup(Base, TimestampMixin, SoftDeleteMixin):
    """Grupo de adicionais de uma Store (ADR-014).

    Exemplos:
    - "Bordas recheadas" (type=single, max_selections=1) — pizza
    - "Frutas" (type=multiple, min_selections=0, max_selections=3) — açaí
    - "Complementos" (type=multiple, min_selections=1, max_selections=5) — açaí

    Pertence a uma Store (grupos são reutilizáveis entre produtos da
    mesma loja via product_addon_groups).

    FK store_id RESTRICT (ADR-011): grupo sobrevive ao soft-delete
    da store (não CASCADE).

    Limites quantitativos:
    - min_selections: 0 = grupo opcional, N = obrigatório escolher N
    - max_selections: quantas opções no máximo o cliente pode pegar
    - CHECK max >= min no banco (garantia de consistência)
    - Pra type=single, max_selections deve ser 1 (validação em camada
      de aplicação, não banco — custo não compensa)
    """

    __tablename__ = "addon_groups"

    id: Mapped[UUIDPK]

    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[AddonGroupType] = mapped_column(String(10), nullable=False)

    min_selections: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_selections: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        CheckConstraint(_ADDON_GROUP_TYPE_CHECK, name="type"),
        CheckConstraint("min_selections >= 0", name="min_selections_non_negative"),
        CheckConstraint(
            "max_selections >= min_selections",
            name="max_selections_gte_min",
        ),
        Index("ix_addon_groups_store_id", "store_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AddonGroup id={self.id} name={self.name!r} type={self.type} "
            f"min={self.min_selections} max={self.max_selections}>"
        )
