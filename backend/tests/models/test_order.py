from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Table,
    UniqueConstraint,
)

from app.db.identifiers import new_public_id
from app.domain.enums import OrderStatus
from app.models.order import _STATUS_CHECK, Order


def _valid_order_kwargs(**overrides: Any) -> dict[str, Any]:
    """Kwargs mínimos pra instanciar Order válido. Overrides opcionais."""
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "public_id": "ISV-ABCD2345",
        "customer_id": uuid4(),
        "store_id": uuid4(),
        "customer_name_snapshot": "João da Silva",
        "delivery_address_line1_snapshot": "Rua das Flores 100",
        "delivery_neighborhood_snapshot": "Centro",
        "delivery_city_snapshot": "Tarumirim",
        "delivery_state_snapshot": "MG",
        "delivery_postal_code_snapshot": "35180000",
        "status": OrderStatus.PENDING,
        "subtotal_cents": 2500,
        "delivery_fee_cents": 500,
        "total_cents": 3000,
    }
    defaults.update(overrides)
    return defaults


class TestOrderStructure:
    def test_has_correct_tablename(self) -> None:
        assert Order.__tablename__ == "orders"

    def test_has_all_20_domain_columns(self) -> None:
        cols = Order.__table__.columns
        expected = {
            "id",
            "public_id",
            "customer_id",
            "store_id",
            "customer_name_snapshot",
            "delivery_address_line1_snapshot",
            "delivery_address_line2_snapshot",
            "delivery_neighborhood_snapshot",
            "delivery_city_snapshot",
            "delivery_state_snapshot",
            "delivery_postal_code_snapshot",
            "delivery_reference_snapshot",
            "status",
            "subtotal_cents",
            "delivery_fee_cents",
            "service_fee_cents",
            "discount_cents",
            "total_cents",
            "coupon_code_snapshot",
            "payment_gateway_transaction_id",
            "notes",
            "confirmed_at",
            "delivered_at",
            "canceled_at",
            "estimated_delivery_at",
        }
        actual = {c.name for c in cols}
        missing = expected - actual
        assert not missing, f"missing columns: {missing}"

    def test_required_columns_not_nullable(self) -> None:
        cols = Order.__table__.columns
        required = (
            "id",
            "public_id",
            "customer_id",
            "store_id",
            "customer_name_snapshot",
            "delivery_address_line1_snapshot",
            "delivery_neighborhood_snapshot",
            "delivery_city_snapshot",
            "delivery_state_snapshot",
            "delivery_postal_code_snapshot",
            "status",
            "subtotal_cents",
            "delivery_fee_cents",
            "service_fee_cents",
            "discount_cents",
            "total_cents",
        )
        for col_name in required:
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_optional_columns_nullable(self) -> None:
        cols = Order.__table__.columns
        optional = (
            "delivery_address_line2_snapshot",
            "delivery_reference_snapshot",
            "coupon_code_snapshot",
            "payment_gateway_transaction_id",
            "notes",
            "confirmed_at",
            "delivered_at",
            "canceled_at",
            "estimated_delivery_at",
        )
        for col_name in optional:
            assert cols[col_name].nullable is True, f"{col_name} should be NULLABLE"

    def test_string_column_lengths(self) -> None:
        cols = Order.__table__.columns
        expected_lengths = {
            "public_id": 12,
            "customer_name_snapshot": 120,
            "delivery_address_line1_snapshot": 200,
            "delivery_address_line2_snapshot": 200,
            "delivery_neighborhood_snapshot": 100,
            "delivery_city_snapshot": 100,
            "delivery_state_snapshot": 2,
            "delivery_postal_code_snapshot": 9,
            "delivery_reference_snapshot": 200,
            "status": 20,
            "coupon_code_snapshot": 50,
            "payment_gateway_transaction_id": 100,
        }
        for col_name, length in expected_lengths.items():
            col_type = cols[col_name].type
            assert isinstance(col_type, String)
            assert col_type.length == length, (
                f"{col_name} expected String({length}), got {col_type.length}"
            )

    def test_cents_columns_are_integer(self) -> None:
        # ADR-007: dinheiro em _cents INTEGER — nunca FLOAT nem DECIMAL
        cols = Order.__table__.columns
        for col_name in (
            "subtotal_cents",
            "delivery_fee_cents",
            "service_fee_cents",
            "discount_cents",
            "total_cents",
        ):
            assert isinstance(cols[col_name].type, Integer)

    def test_timestamp_columns_are_timezone_aware(self) -> None:
        cols = Order.__table__.columns
        for col_name in (
            "confirmed_at",
            "delivered_at",
            "canceled_at",
            "estimated_delivery_at",
        ):
            col_type = cols[col_name].type
            assert isinstance(col_type, DateTime)
            assert col_type.timezone is True

    def test_public_id_has_callable_default(self) -> None:
        # ADR-018: default via lambda calling new_public_id("ISV")
        col = Order.__table__.columns["public_id"]
        assert col.default is not None
        assert callable(col.default.arg)

    def test_public_id_column_is_varchar_12(self) -> None:
        """ADR-003: public_id é VARCHAR(12) — 'ISV-' (4) + 8 chars = 12."""
        table = Order.__table__
        assert isinstance(table, Table)
        public_id_col = table.c.public_id
        assert isinstance(public_id_col.type, String)
        assert public_id_col.type.length == 12

    def test_status_default_is_pending(self) -> None:
        col = Order.__table__.columns["status"]
        assert col.default is not None
        assert col.default.arg == OrderStatus.PENDING
        assert col.server_default is not None

    def test_service_fee_and_discount_default_zero(self) -> None:
        cols = Order.__table__.columns
        for col_name in ("service_fee_cents", "discount_cents"):
            col = cols[col_name]
            assert col.default is not None
            assert col.default.arg == 0
            assert col.server_default is not None

    def test_fk_customer_id_restrict(self) -> None:
        # ADR-011: FK de entidade usa RESTRICT
        table = Order.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["customer_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "customers"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT"

    def test_fk_store_id_restrict(self) -> None:
        # ADR-011: FK de entidade usa RESTRICT
        table = Order.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["store_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "stores"
        assert fk.column.name == "id"
        assert fk.ondelete == "RESTRICT"

    def test_has_six_check_constraints(self) -> None:
        table = Order.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        assert len(checks) == 6, f"expected 6 CHECKs, got {len(checks)}"

    def test_check_status_contains_all_enum_values(self) -> None:
        table = Order.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        status_check = next((c for c in checks if c.name == "ck_orders_status_valid"), None)
        assert status_check is not None, "ck_orders_status_valid not found"
        sql_text = str(status_check.sqltext)
        for value in (
            "pending",
            "confirmed",
            "preparing",
            "out_for_delivery",
            "delivered",
            "canceled",
            "payment_failed",
        ):
            assert f"'{value}'" in sql_text, f"CHECK missing status value: {value}"

    def test_checks_non_negative_cents_present(self) -> None:
        table = Order.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        check_names = {c.name for c in checks if isinstance(c.name, str)}
        expected_names = {
            "ck_orders_subtotal_cents_non_negative",
            "ck_orders_delivery_fee_cents_non_negative",
            "ck_orders_service_fee_cents_non_negative",
            "ck_orders_discount_cents_non_negative",
            "ck_orders_total_cents_non_negative",
        }
        assert expected_names.issubset(check_names), (
            f"missing CHECKs: {expected_names - check_names}"
        )

    def test_unique_constraint_on_public_id(self) -> None:
        table = Order.__table__
        assert isinstance(table, Table)
        uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        pub_unique = next((c for c in uniques if c.name == "uq_orders_public_id"), None)
        assert pub_unique is not None, "uq_orders_public_id not found"
        assert {col.name for col in pub_unique.columns} == {"public_id"}

    def test_partial_unique_on_payment_gateway_transaction_id(self) -> None:
        # ADR-017 R3: UNIQUE parcial via Index(..., unique=True, postgresql_where=...)
        table = Order.__table__
        assert isinstance(table, Table)
        ix = next(
            (i for i in table.indexes if i.name == "uq_orders_payment_gateway_transaction_id"),
            None,
        )
        assert ix is not None, "uq_orders_payment_gateway_transaction_id not found"
        assert ix.unique is True
        where_clause = ix.dialect_kwargs.get("postgresql_where")
        assert where_clause is not None
        assert "payment_gateway_transaction_id IS NOT NULL" in str(where_clause)

    def test_three_non_unique_indexes_present(self) -> None:
        table = Order.__table__
        assert isinstance(table, Table)
        for ix_name in (
            "ix_orders_customer_id",
            "ix_orders_store_id",
            "ix_orders_status",
        ):
            ix = next((i for i in table.indexes if i.name == ix_name), None)
            assert ix is not None, f"missing index: {ix_name}"


class TestOrderBehavior:
    def test_order_status_enum_values(self) -> None:
        assert {v.value for v in OrderStatus} == {
            "pending",
            "confirmed",
            "preparing",
            "out_for_delivery",
            "delivered",
            "canceled",
            "payment_failed",
        }

    def test_repr_contains_id_public_id_status_store_total(self) -> None:
        order = Order(**_valid_order_kwargs())
        r = repr(order)
        assert "ISV-ABCD2345" in r
        assert "pending" in r.lower()
        assert str(order.store_id) in r
        assert "3000" in r  # total_cents

    def test_repr_does_not_expose_customer_or_address_or_notes(self) -> None:
        order = Order(**_valid_order_kwargs(notes="Allergy: peanuts"))
        r = repr(order)
        assert "João" not in r
        assert "Rua das Flores" not in r
        assert "35180000" not in r
        assert "Tarumirim" not in r
        assert "Allergy" not in r

    def test_composes_timestamp_mixin(self) -> None:
        cols = Order.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_composes_soft_delete_mixin(self) -> None:
        cols = Order.__table__.columns
        assert "deleted_at" in cols
        assert cols["deleted_at"].nullable is True


class TestOrderStatusCheckDynamic:
    """Regressão ADR-006: _STATUS_CHECK reconstruído do StrEnum.

    Se OrderStatus ganhar valor novo no futuro, este teste garante que o
    CHECK constraint gerado reflete todos os valores sem precisar atualizar
    código manualmente.
    """

    def test_status_check_contains_all_enum_values(self) -> None:
        for value in (
            "pending",
            "confirmed",
            "preparing",
            "out_for_delivery",
            "delivered",
            "canceled",
            "payment_failed",
        ):
            assert f"'{value}'" in _STATUS_CHECK


class TestPublicIdFormat:
    """ADR-018: formato ISV-XXXXXXXX, 8 chars sobre alfabeto reduzido de 31.

    Alfabeto exclui 0, O, I, L, 1 pra evitar ambiguidade visual e em
    ditado por telefone.
    """

    ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    FORBIDDEN = frozenset("0O1IL")

    def test_starts_with_isv_prefix(self) -> None:
        result = new_public_id("ISV")
        assert result.startswith("ISV-")

    def test_total_length_is_12(self) -> None:
        result = new_public_id("ISV")
        # "ISV-" (4 chars) + sufixo (8 chars) = 12
        assert len(result) == 12

    def test_suffix_length_is_8(self) -> None:
        result = new_public_id("ISV")
        suffix = result.split("-", 1)[1]
        assert len(suffix) == 8

    def test_suffix_chars_in_reduced_alphabet(self) -> None:
        result = new_public_id("ISV")
        suffix = result.split("-", 1)[1]
        for ch in suffix:
            assert ch in self.ALPHABET, f"char {ch!r} not in reduced alphabet"

    def test_no_forbidden_chars_in_bulk(self) -> None:
        for _ in range(200):
            result = new_public_id("ISV")
            suffix = result.split("-", 1)[1]
            assert not (set(suffix) & self.FORBIDDEN), f"forbidden char found in {result!r}"

    def test_two_consecutive_calls_differ(self) -> None:
        a = new_public_id("ISV")
        b = new_public_id("ISV")
        assert a != b
