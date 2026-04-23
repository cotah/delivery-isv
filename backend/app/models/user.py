from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.db.types import UUIDPK
from app.utils.validators import validate_phone_e164


class User(Base, TimestampMixin):
    """Identidade de usuário autenticado via OTP SMS (ADR-025).

    User representa identidade pura: telefone E.164 (ADR-009) validado
    via OTP (ADR-025 decisão 1). Perfil mutável (nome, preferências,
    endereços) fica em Customer — ponte entre User e Customer será
    adicionada em ciclo dedicado (débito MEDIUM pré-piloto, ADR-025
    dívida técnica #1).

    Sem SoftDeleteMixin no MVP — delete de User é tema do ciclo LGPD
    (ADR futuro). Anonimização via endpoint admin virá junto.

    User é criado lazy — só após verify-otp bem-sucedido (ADR-025
    decisão 6). Request-otp NÃO cria User; consulta apenas OtpCode.
    """

    __tablename__ = "users"

    id: Mapped[UUIDPK]
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    @validates("phone")
    def _validate_phone(self, _key: str, value: str) -> str:
        return validate_phone_e164(value)

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone}>"
