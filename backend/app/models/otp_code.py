from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.db.types import UUIDPK
from app.utils.validators import validate_phone_e164


class OtpCode(Base, TimestampMixin):
    """Código OTP descartável para autenticação SMS (ADR-025 decisão 2).

    OtpCode é criado no endpoint request-otp, consumido no verify-otp.
    Armazena apenas sha256 hash do código cru (ADR-025 decisão 3) —
    nunca guarda código em texto plano.

    Campos:
    - phone: telefone E.164 alvo do OTP (não é FK de User porque OtpCode
      é criado antes de User existir — lazy user creation, decisão 6)
    - code_hash: sha256 hexdigest (64 chars fixos)
    - expires_at: setado em runtime (now + 10min, decisão 4)
    - consumed_at: null até verify-otp bem-sucedido; setado ao consumir
    - attempts: incrementa a cada verify-otp, mesmo se falhar (limite 3,
      decisão 5)

    Sem SoftDeleteMixin — OTP é dado efêmero. Job de cleanup de registros
    antigos entra como débito operacional LOW (ADR-025 dívida técnica #5).

    Índice composto (phone, expires_at) acelera query quente:
    "código mais recente ativo para este telefone".
    """

    __tablename__ = "otp_codes"

    id: Mapped[UUIDPK]
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        Index("ix_otp_codes_phone_expires_at", "phone", "expires_at"),
    )

    @validates("phone")
    def _validate_phone(self, _key: str, value: str) -> str:
        return validate_phone_e164(value)

    def __repr__(self) -> str:
        return (
            f"<OtpCode id={self.id} phone={self.phone} "
            f"expires_at={self.expires_at} consumed={self.consumed_at is not None} "
            f"attempts={self.attempts}>"
        )
