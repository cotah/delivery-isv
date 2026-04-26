from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.db.types import UUIDPK
from app.utils.validators import validate_phone_e164

if TYPE_CHECKING:
    from app.models.customer import Customer


class User(Base, TimestampMixin):
    """Identidade de usuário autenticado via OTP SMS (ADR-025).

    User representa identidade pura: telefone E.164 (ADR-009) validado
    via OTP (ADR-025 decisão 1). Perfil mutável (nome, preferências,
    endereços) fica em Customer.

    Conexão com Customer via FK Customer.user_id (ADR-027 dec. 1).
    User existe sem Customer até o cliente fazer POST /customers
    (lazy creation, ADR-027 dec. 2). Relationship customer abaixo é
    Optional (None se ainda não cadastrou perfil).

    Sem SoftDeleteMixin no MVP — delete de User é tema do ciclo LGPD
    (ADR futuro). Anonimização via endpoint admin virá junto.

    User é criado lazy — só após verify-otp bem-sucedido (ADR-025
    decisão 6). Request-otp NÃO cria User; consulta apenas OtpCode.
    """

    __tablename__ = "users"

    id: Mapped[UUIDPK]
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # ORM relationship 1:1 opcional pra Customer (ADR-027 dec. 1, dec. 15).
    # uselist=False força singular (User → 0..1 Customer) — pattern novo
    # do projeto pra 1:1 do lado da PK (sem FK no lado do User; FK fica
    # no Customer.user_id). Sem isso, SQLAlchemy retornaria coleção.
    # lazy="raise" pattern projeto (force eager load explícito).
    # foreign_keys explícito pra blindar contra ambiguidade futura (ADR-027
    # dec. 15) — se algum dia houver múltiplas FKs users<->customers, a
    # inferência automática pode escolher errado silenciosamente.
    customer: Mapped["Customer | None"] = relationship(
        "Customer",
        lazy="raise",
        uselist=False,
        foreign_keys="[Customer.user_id]",
    )

    @validates("phone")
    def _validate_phone(self, _key: str, value: str) -> str:
        return validate_phone_e164(value)

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone}>"
