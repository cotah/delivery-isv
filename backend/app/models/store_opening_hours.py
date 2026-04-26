from datetime import time
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.db.types import UUIDPK


class StoreOpeningHours(Base, TimestampMixin):
    """Slot de horário de funcionamento de uma loja (ADR-026 dec. 1).

    1 row por slot. Loja pode ter múltiplos slots no mesmo dia (almoço/jantar).
    Loja fechada num dia: zero rows pra esse `day_of_week` (ADR-026 dec. 4).

    `day_of_week` segue convenção Postgres EXTRACT(DOW) (ADR-026 reforço D1):
    - 0 = domingo
    - 1 = segunda
    - 6 = sábado

    NÃO usar `datetime.weekday()` (0=segunda) ao popular ou consultar — gera
    bug silencioso. Conversão segura: `dt.isoweekday() % 7`.

    Cruzar meia-noite: 1 row com `close_time < open_time` (ADR-026 dec. 3).
    Ex: pizzaria 18h-02h = `open_time=18:00, close_time=02:00`.

    Sem SoftDeleteMixin (ADR-026 dec. — D2 do CP1b): DELETE simples + CASCADE
    da Store basta. Slot inativo = lojista deletou e recadastrou.

    UNIQUE `(store_id, day_of_week, open_time)` protege contra duplicatas
    exatas. NÃO protege overlaps parciais — validação deferida pro painel
    admin (ADR-026 reforço D4 — débito diferido `validate_no_overlap`).
    """

    __tablename__ = "store_opening_hours"

    id: Mapped[UUIDPK]

    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Postgres DOW: 0=domingo..6=sábado. NUNCA datetime.weekday() (ADR-026 reforço D1).
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)

    open_time: Mapped[time] = mapped_column(Time, nullable=False)
    close_time: Mapped[time] = mapped_column(Time, nullable=False)

    __table_args__ = (
        # CHECKs: passar SÓ sufixo (naming_convention prefixa ck_<table>_).
        CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="day_of_week_valid_range",
        ),
        CheckConstraint(
            "open_time != close_time",
            name="open_time_close_time_different",
        ),
        # UniqueConstraint multi-coluna: nome COMPLETO (CLAUDE.md armadilha #2 —
        # naming_convention uq_ só pega a 1ª coluna).
        UniqueConstraint(
            "store_id",
            "day_of_week",
            "open_time",
            name="uq_store_opening_hours_store_id_day_of_week_open_time",
        ),
        # Index multi-coluna: nome COMPLETO (mesma razão da UniqueConstraint).
        # Acelera query "aberto agora?" (filtra por store_id + day_of_week).
        Index(
            "ix_store_opening_hours_store_id_day_of_week",
            "store_id",
            "day_of_week",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<StoreOpeningHours id={self.id} "
            f"store_id={self.store_id} "
            f"day={self.day_of_week} "
            f"{self.open_time}-{self.close_time}>"
        )
