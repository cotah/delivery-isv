from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adiciona created_at e updated_at em TIMESTAMPTZ.

    Conforme ADR-005:
    - TIMESTAMPTZ (with timezone) — evita bugs de fuso horário
    - server_default=func.now() — banco preenche (fonte única de relógio)
    - onupdate=func.now() no updated_at — banco atualiza em cada UPDATE

    Aplicar em todos os modelos de dado mutável.
    Modelos de log imutável devem usar só CreatedAtMixin.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adiciona deleted_at (TIMESTAMPTZ nullable) para soft delete.

    Conforme ADR-004:
    - NULL = registro ativo
    - Preenchido com timestamp = registro soft-deletado
    - Queries padrão devem filtrar WHERE deleted_at IS NULL
    - Para LGPD "direito ao esquecimento", aplicar anonimização de PII
      em conjunto com soft delete (código da anonimização virá depois,
      junto com os modelos específicos que têm PII).
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class CreatedAtMixin:
    """Adiciona só created_at, sem updated_at.

    Para tabelas de log imutável (admin_logs, order_status_logs,
    notifications, cart_items) conforme ADR-004/005.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
