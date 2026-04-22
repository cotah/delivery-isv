from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import CreatedAtMixin
from app.db.types import UUIDPK
from app.domain.enums import OrderStatus

# CHECK constraints gerados dinamicamente do enum (ADR-006, ADR-019).
# _FROM_STATUS_CHECK precisa começar com "from_status IS NULL OR" porque a
# primeira entrada do log representa a criação do pedido (sem estado anterior).
# Sem esse prefixo, o INSERT inicial quebra no banco.
_FROM_STATUS_CHECK = (
    "from_status IS NULL OR from_status IN (" + ", ".join(f"'{s.value}'" for s in OrderStatus) + ")"
)

_TO_STATUS_CHECK = "to_status IN (" + ", ".join(f"'{s.value}'" for s in OrderStatus) + ")"


class OrderStatusLog(Base, CreatedAtMixin):
    """Log append-only de transições de status de um Order (ADR-003, ADR-015, ADR-017, ADR-019).

    Primeiro modelo append-only do projeto (ADR-019). Cada transição de status
    de um Order gera uma entrada nova e imutável aqui — nunca atualizada,
    nunca soft-deletada. Por isso compõe apenas CreatedAtMixin, sem
    TimestampMixin nem SoftDeleteMixin (combinação mutuamente exclusiva).

    Relacionamento (ADR-015):
    - order_id -> orders.id (CASCADE — log é parte indissociável do pedido:
      se o Order é hard-deletado, seus logs somem junto).

    Transição (ADR-017 + ADR-019):
    - from_status NULLABLE: primeira entrada do log representa a criação do
      pedido, quando não há estado anterior. Semântica: from_status IS NULL
      significa "criação do pedido".
    - to_status NOT NULL: toda transição tem destino.
    - reason livre (Text): motivo textual preenchido pelo lojista/admin
      (ex: "cliente desistiu" em cancelamento). Categorização estrutural
      fica pra feature futura.

    CHECKs dinâmicos (ADR-006):
    - from_status: "IS NULL OR IN (...)" aceita criação do pedido e
      transições válidas. Armadilha documentada no ADR-019: os 10 modelos
      anteriores só tinham enums NOT NULL, então copiar o pattern deles
      cegamente quebra a primeira inserção.
    - to_status: só "IN (...)" porque é NOT NULL.

    TODO: adicionar changed_by_user_id quando modelo User/Auth existir
    (ADR futuro).
    """

    __tablename__ = "order_status_logs"

    # Identidade
    id: Mapped[UUIDPK]

    # FK CASCADE — log é parte indissociável do Order (ADR-015)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Transição de estado (ADR-017 + ADR-019)
    # from_status NULLABLE: primeira entrada do log é criação do pedido (sem estado anterior)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)

    # Motivo livre (ex: "cliente desistiu" em cancelamento)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # TODO: adicionar changed_by_user_id quando modelo User/Auth existir (ADR futuro).

    __table_args__ = (
        CheckConstraint(_FROM_STATUS_CHECK, name="from_status_valid"),
        CheckConstraint(_TO_STATUS_CHECK, name="to_status_valid"),
        Index("ix_order_status_logs_order_id", "order_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrderStatusLog id={self.id} order_id={self.order_id} "
            f"from_status={self.from_status!r} to_status={self.to_status!r}>"
        )
