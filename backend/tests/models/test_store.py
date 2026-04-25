from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, Table

from app.domain.enums import StoreStatus, TaxIdType
from app.models.store import Store

VALID_CPF = "52998224725"
VALID_CNPJ = "11222333000181"


def _valid_store_kwargs(**overrides: Any) -> dict[str, Any]:
    """Kwargs mínimos pra instanciar Store válido. Overrides opcionais."""
    defaults: dict[str, Any] = {
        "legal_name": "Marmitaria da Maria LTDA",
        "trade_name": "Marmitaria da Maria",
        "tax_id": VALID_CPF,
        "tax_id_type": "cpf",
        "slug": "marmitaria-da-maria",
        "category_id": uuid4(),
        "city_id": uuid4(),
        "street": "Rua das Flores",
        "number": "100",
        "neighborhood": "Centro",
        "zip_code": "35180000",
    }
    defaults.update(overrides)
    return defaults


class TestStoreStructure:
    def test_has_correct_tablename(self) -> None:
        assert Store.__tablename__ == "stores"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = Store.__table__.columns
        required = (
            "id",
            "legal_name",
            "trade_name",
            "tax_id",
            "tax_id_type",
            "slug",
            "status",
            "is_active",
            "category_id",
            "city_id",
            "street",
            "number",
            "neighborhood",
            "zip_code",
        )
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_optional_column_nullable(self) -> None:
        cols = Store.__table__.columns
        assert "complement" in cols
        assert cols["complement"].nullable is True

    def test_has_soft_delete(self) -> None:
        cols = Store.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True

    def test_has_timestamps(self) -> None:
        cols = Store.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_tax_id_is_unique(self) -> None:
        assert Store.__table__.columns["tax_id"].unique is True

    def test_slug_is_unique(self) -> None:
        assert Store.__table__.columns["slug"].unique is True

    def test_has_fk_to_categories(self) -> None:
        table = Store.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["category_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "categories"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT"

    def test_has_fk_to_cities(self) -> None:
        table = Store.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["city_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "cities"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT"

    def test_has_check_constraint_on_status(self) -> None:
        table = Store.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        status_check = next((c for c in checks if c.name == "ck_stores_status"), None)
        assert status_check is not None, "ck_stores_status not found"
        sql_text = str(status_check.sqltext)
        for value in ("pending", "approved", "rejected", "blocked", "paused"):
            assert f"'{value}'" in sql_text, f"CHECK missing status value: {value}"

    def test_has_check_constraint_on_tax_id_type(self) -> None:
        table = Store.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        tax_id_check = next(
            (c for c in checks if c.name == "ck_stores_tax_id_type"),
            None,
        )
        assert tax_id_check is not None, "ck_stores_tax_id_type not found"
        sql_text = str(tax_id_check.sqltext)
        for value in ("cpf", "cnpj"):
            assert f"'{value}'" in sql_text, f"CHECK missing tax_id_type value: {value}"

    def test_has_index_on_category_id(self) -> None:
        table = Store.__table__
        assert isinstance(table, Table)
        ix = next((i for i in table.indexes if i.name == "ix_stores_category_id"), None)
        assert ix is not None

    def test_has_index_on_city_id(self) -> None:
        table = Store.__table__
        assert isinstance(table, Table)
        ix = next((i for i in table.indexes if i.name == "ix_stores_city_id"), None)
        assert ix is not None

    def test_has_index_on_status(self) -> None:
        table = Store.__table__
        assert isinstance(table, Table)
        ix = next((i for i in table.indexes if i.name == "ix_stores_status"), None)
        assert ix is not None

    def test_status_default_is_pending(self) -> None:
        col = Store.__table__.columns["status"]
        # Python default (usado quando ORM cria sem passar status)
        assert col.default is not None
        assert col.default.arg == StoreStatus.PENDING
        # DB-side server_default (usado em raw SQL / seeds)
        assert col.server_default is not None


class TestStoreBehavior:
    def test_store_status_enum_values(self) -> None:
        assert {v.value for v in StoreStatus} == {
            "pending",
            "approved",
            "rejected",
            "blocked",
            "paused",
        }

    def test_tax_id_type_enum_values(self) -> None:
        assert {v.value for v in TaxIdType} == {"cpf", "cnpj"}

    def test_validator_rejects_cpf_with_cnpj_type(self) -> None:
        # CPF válido (11 dígitos) com tax_id_type="cnpj" → validate_cnpj exige 14
        with pytest.raises(ValueError, match="14 digits"):
            Store(**_valid_store_kwargs(tax_id=VALID_CPF, tax_id_type="cnpj"))

    def test_validator_rejects_cnpj_with_cpf_type(self) -> None:
        # CNPJ válido (14 dígitos) com tax_id_type="cpf" → validate_cpf exige 11
        with pytest.raises(ValueError, match="11 digits"):
            Store(**_valid_store_kwargs(tax_id=VALID_CNPJ, tax_id_type="cpf"))

    def test_validator_accepts_valid_cpf_with_cpf_type(self) -> None:
        store = Store(**_valid_store_kwargs(tax_id=VALID_CPF, tax_id_type="cpf"))
        assert store.tax_id == VALID_CPF

    def test_validator_accepts_valid_cnpj_with_cnpj_type(self) -> None:
        store = Store(**_valid_store_kwargs(tax_id=VALID_CNPJ, tax_id_type="cnpj"))
        assert store.tax_id == VALID_CNPJ

    def test_repr_masks_tax_id(self) -> None:
        store = Store(
            **_valid_store_kwargs(tax_id=VALID_CPF, tax_id_type="cpf", phone="+5531999887766")
        )
        r = repr(store)
        # Não expõe tax_id completo
        assert VALID_CPF not in r
        # Mostra slug (legível)
        assert "marmitaria-da-maria" in r
        # Mascara aplicada (formato CPF mascarado)
        assert "529.***.***-25" in r


VALID_PHONE = "+5531999887766"


class TestStoreExtensionFields:
    """Campos adicionados no CP1a do Ciclo Débitos HIGH #1 (ADR-026, 2026-04-26)."""

    def test_description_is_text_nullable(self) -> None:
        cols = Store.__table__.columns
        assert "description" in cols
        assert cols["description"].nullable is True
        # Type Text (sem cap no DB — validação max_length=2000 fica no schema Pydantic).
        assert str(cols["description"].type).upper() == "TEXT"

    def test_description_default_none_when_not_set(self) -> None:
        store = Store(**_valid_store_kwargs(phone=VALID_PHONE))
        assert store.description is None

    def test_description_accepts_long_text(self) -> None:
        long_text = "A" * 1500
        store = Store(**_valid_store_kwargs(phone=VALID_PHONE, description=long_text))
        assert store.description == long_text

    def test_phone_is_string_20_not_null(self) -> None:
        cols = Store.__table__.columns
        assert "phone" in cols
        assert cols["phone"].nullable is False
        assert str(cols["phone"].type) == "VARCHAR(20)"

    def test_phone_validates_e164_via_validates(self) -> None:
        # Sem +, sem código país — rejeita.
        with pytest.raises(ValueError, match=r"E\.164"):
            Store(**_valid_store_kwargs(phone="11999887766"))

    def test_phone_rejects_letters(self) -> None:
        with pytest.raises(ValueError, match=r"E\.164"):
            Store(**_valid_store_kwargs(phone="+ABCDEFGHIJK"))

    def test_phone_accepts_valid_e164_brazilian(self) -> None:
        store = Store(**_valid_store_kwargs(phone="+5531999887766"))
        assert store.phone == "+5531999887766"

    def test_phone_accepts_valid_e164_international(self) -> None:
        # Pattern E.164 aceita qualquer país (não-BR).
        store = Store(**_valid_store_kwargs(phone="+14155552671"))
        assert store.phone == "+14155552671"

    def test_minimum_order_cents_is_integer_nullable(self) -> None:
        cols = Store.__table__.columns
        assert "minimum_order_cents" in cols
        assert cols["minimum_order_cents"].nullable is True
        assert "INTEGER" in str(cols["minimum_order_cents"].type).upper()

    def test_minimum_order_cents_default_none(self) -> None:
        store = Store(**_valid_store_kwargs(phone=VALID_PHONE))
        assert store.minimum_order_cents is None

    def test_minimum_order_cents_zero_accepted(self) -> None:
        store = Store(**_valid_store_kwargs(phone=VALID_PHONE, minimum_order_cents=0))
        assert store.minimum_order_cents == 0

    def test_minimum_order_cents_positive_accepted(self) -> None:
        store = Store(**_valid_store_kwargs(phone=VALID_PHONE, minimum_order_cents=2500))
        assert store.minimum_order_cents == 2500

    def test_has_check_constraint_minimum_order_cents_non_negative(self) -> None:
        table = Store.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        check = next(
            (c for c in checks if c.name == "ck_stores_minimum_order_cents_non_negative"),
            None,
        )
        assert check is not None, "ck_stores_minimum_order_cents_non_negative not found"
        sql_text = str(check.sqltext)
        # NULL-safe + non-negative.
        assert "minimum_order_cents" in sql_text
        assert "IS NULL" in sql_text
        assert ">= 0" in sql_text

    def test_cover_image_is_string_500_nullable(self) -> None:
        cols = Store.__table__.columns
        assert "cover_image" in cols
        assert cols["cover_image"].nullable is True
        assert str(cols["cover_image"].type) == "VARCHAR(500)"

    def test_cover_image_default_none(self) -> None:
        store = Store(**_valid_store_kwargs(phone=VALID_PHONE))
        assert store.cover_image is None

    def test_logo_is_string_500_nullable(self) -> None:
        cols = Store.__table__.columns
        assert "logo" in cols
        assert cols["logo"].nullable is True
        assert str(cols["logo"].type) == "VARCHAR(500)"

    def test_logo_default_none(self) -> None:
        store = Store(**_valid_store_kwargs(phone=VALID_PHONE))
        assert store.logo is None

    def test_repr_masks_phone_proactive_lgpd(self) -> None:
        """ADR-026 dec. 8 — Store antecipa débito LGPD do User."""
        store = Store(**_valid_store_kwargs(phone="+5531999887766"))
        r = repr(store)
        # Não expõe phone cru
        assert "+5531999887766" not in r
        # Aplica máscara mask_phone_for_log: formato +55*********66
        assert "+55*********66" in r
