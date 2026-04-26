from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import UUIDPK
from app.domain.enums import StoreStatus, TaxIdType
from app.utils.validators import (
    mask_phone_for_log,
    mask_tax_id_for_log,
    validate_phone_e164,
    validate_tax_id,
)

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.city import City
    from app.models.store_opening_hours import StoreOpeningHours

# CHECK constraints geradas dinamicamente dos enums (fonte única de verdade)
_STATUS_CHECK = "status IN (" + ", ".join(f"'{s.value}'" for s in StoreStatus) + ")"
_TAX_ID_TYPE_CHECK = "tax_id_type IN (" + ", ".join(f"'{t.value}'" for t in TaxIdType) + ")"


class Store(Base, TimestampMixin, SoftDeleteMixin):
    """Lojista (restaurante, padaria, etc.) cadastrado no ISV Delivery.

    Identificação fiscal híbrida (ADR-012): tax_id aceita CPF (11 dígitos)
    ou CNPJ (14 dígitos), conforme tax_id_type declarado. Validação
    cruzada via @validates (defense-in-depth, ADR-010).

    Relacionamentos:
    - category_id → categories.id (RESTRICT — não deleta categoria em uso)
    - city_id → cities.id (RESTRICT — consistente com Address)

    Status operacional (ADR-006 via StrEnum + CHECK):
    pending → approved/rejected, approved ↔ paused, approved ↔ blocked.

    Endereço fixo da loja (não reusa Address pra evitar dependência com
    Customer). Decisões de negócio (comissão, taxa, horário, delivery mode)
    ficam em modelos separados quando o sócio decidir.
    """

    __tablename__ = "stores"

    id: Mapped[UUIDPK]

    # Identificação
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(14), nullable=False, unique=True)
    tax_id_type: Mapped[TaxIdType] = mapped_column(String(4), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)

    # Status e flags
    status: Mapped[StoreStatus] = mapped_column(
        String(20),
        nullable=False,
        default=StoreStatus.PENDING,
        server_default=StoreStatus.PENDING.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Relacionamentos
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    city_id: Mapped[UUID] = mapped_column(
        ForeignKey("cities.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ORM relationships — lazy="raise" obriga eager load explícito (selectinload/
    # joinedload). Query sem eager load levanta InvalidRequestError em vez de
    # silenciosamente disparar N+1 query por linha.
    category: Mapped["Category"] = relationship("Category", lazy="raise")
    city: Mapped["City"] = relationship("City", lazy="raise")
    # Slots de horário (ADR-026 dec. 1, CP1b 2026-04-26). Cascade de DELETE é
    # garantido no DB via FK ondelete=CASCADE — não precisa cascade Python.
    # order_by garante slots determinísticos no response (frontend agrupa por dia).
    opening_hours: Mapped[list["StoreOpeningHours"]] = relationship(
        "StoreOpeningHours",
        lazy="raise",
        order_by="StoreOpeningHours.day_of_week, StoreOpeningHours.open_time",
    )

    # Endereço textual (não reusa Address — ver docstring)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    complement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    neighborhood: Mapped[str] = mapped_column(String(100), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(8), nullable=False)

    # Expansão pré-piloto (ADR-026, HIGH debt #1, CP1a 2026-04-26).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    minimum_order_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="status"),
        CheckConstraint(_TAX_ID_TYPE_CHECK, name="tax_id_type"),
        # NULL-safe: minimum_order é opcional. Pattern price_cents (ADR-007).
        CheckConstraint(
            "minimum_order_cents IS NULL OR minimum_order_cents >= 0",
            name="minimum_order_cents_non_negative",
        ),
        Index("ix_stores_category_id", "category_id"),
        Index("ix_stores_city_id", "city_id"),
        Index("ix_stores_status", "status"),
    )

    @validates("phone")
    def _validate_phone(self, _key: str, value: str) -> str:
        """Defense-in-depth (ADR-010, ADR-026 dec. 5) — rejeita phone fora E.164."""
        return validate_phone_e164(value)

    @validates("tax_id", "tax_id_type")
    def _validate_tax_id_fields(self, key: str, value: str) -> str:
        """Validação cruzada tax_id + tax_id_type (ADR-010, ADR-012).

        Chamado a cada assignment, independente da ordem. Só valida
        quando ambos os campos já estiverem setados.
        """
        # Tipos unidos explicitamente — nos 2 branches uma das variáveis
        # recebe `value` (str) e a outra pode ser None se ainda não setado.
        tax_id: str | None
        tax_id_type_val: str | TaxIdType | None

        if key == "tax_id":
            tax_id = value
            tax_id_type_val = self.tax_id_type if hasattr(self, "tax_id_type") else None
        else:  # key == "tax_id_type"
            tax_id_type_val = value
            tax_id = self.tax_id if hasattr(self, "tax_id") else None

        # Se ambos setados, valida cruzado
        if tax_id and tax_id_type_val:
            validate_tax_id(tax_id, str(tax_id_type_val))

        return value

    def __repr__(self) -> str:
        # phone mascarado proativamente (ADR-026 dec. 8 — antecipa débito LGPD).
        phone = getattr(self, "phone", None)
        return (
            f"<Store id={self.id} slug={self.slug} "
            f"tax_id={mask_tax_id_for_log(self.tax_id, str(self.tax_id_type))} "
            f"phone={mask_phone_for_log(phone)}>"
        )
