from typing import Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, String, Table, Text, UniqueConstraint

from app.domain.enums import OrderStatus
from app.models.order_status_log import (
    _FROM_STATUS_CHECK,
    _TO_STATUS_CHECK,
    OrderStatusLog,
)


def _valid_order_status_log_kwargs(**overrides: Any) -> dict[str, Any]:
    """Kwargs mínimos pra instanciar OrderStatusLog válido. Overrides opcionais."""
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "order_id": uuid4(),
        "from_status": None,
        "to_status": OrderStatus.PENDING.value,
        "reason": None,
    }
    defaults.update(overrides)
    return defaults


class TestOrderStatusLogStructure:
    def test_has_correct_tablename(self) -> None:
        assert OrderStatusLog.__tablename__ == "order_status_logs"

    def test_has_all_5_domain_columns(self) -> None:
        cols = OrderStatusLog.__table__.columns
        expected = {
            "id",
            "order_id",
            "from_status",
            "to_status",
            "reason",
        }
        actual = {c.name for c in cols}
        missing = expected - actual
        assert not missing, f"missing columns: {missing}"

    def test_total_column_count_is_six(self) -> None:
        """5 de domínio + created_at (CreatedAtMixin) = 6. Zero updated_at/deleted_at."""
        cols = OrderStatusLog.__table__.columns
        assert len(cols) == 6, f"expected 6 columns (5 domain + created_at), got {len(cols)}"

    def test_required_columns_not_nullable(self) -> None:
        cols = OrderStatusLog.__table__.columns
        for col_name in ("id", "order_id", "to_status"):
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_optional_columns_nullable(self) -> None:
        cols = OrderStatusLog.__table__.columns
        for col_name in ("from_status", "reason"):
            assert cols[col_name].nullable is True, f"{col_name} should be NULLABLE"

    def test_from_status_and_to_status_are_varchar_20(self) -> None:
        cols = OrderStatusLog.__table__.columns
        for col_name in ("from_status", "to_status"):
            col_type = cols[col_name].type
            assert isinstance(col_type, String)
            assert col_type.length == 20, f"{col_name} expected String(20), got {col_type.length}"

    def test_reason_is_text(self) -> None:
        col = OrderStatusLog.__table__.columns["reason"]
        assert isinstance(col.type, Text)

    def test_fk_order_id_cascade(self) -> None:
        # ADR-015: log é composição estrita do Order — CASCADE
        table = OrderStatusLog.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["order_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "orders"
        assert fk.column.name == "id"
        assert fk.ondelete == "CASCADE", f"ADR-015: expected CASCADE, got {fk.ondelete!r}"

    def test_has_two_check_constraints(self) -> None:
        table = OrderStatusLog.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        assert len(checks) == 2, f"expected 2 CHECKs, got {len(checks)}"

    def test_check_names_with_naming_convention_prefix(self) -> None:
        """naming_convention aplica ck_<table>_ a partir do sufixo literal."""
        table = OrderStatusLog.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        names = {c.name for c in checks if isinstance(c.name, str)}
        expected = {
            "ck_order_status_logs_from_status_valid",
            "ck_order_status_logs_to_status_valid",
        }
        assert expected.issubset(names), f"missing: {expected - names}"

    def test_has_one_non_unique_index(self) -> None:
        table = OrderStatusLog.__table__
        assert isinstance(table, Table)
        ix = next(
            (i for i in table.indexes if i.name == "ix_order_status_logs_order_id"),
            None,
        )
        assert ix is not None, "missing index ix_order_status_logs_order_id"
        assert ix.unique is False

    def test_no_unique_constraint(self) -> None:
        table = OrderStatusLog.__table__
        assert isinstance(table, Table)
        uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        assert len(uniques) == 0, f"unexpected UNIQUE constraints: {uniques}"

    def test_no_updated_at_column(self) -> None:
        """Regressão ADR-019: modelo append-only NÃO tem updated_at."""
        cols = OrderStatusLog.__table__.columns
        assert "updated_at" not in cols, "append-only model must not have updated_at"

    def test_no_deleted_at_column(self) -> None:
        """Regressão ADR-019: modelo append-only NÃO tem deleted_at."""
        cols = OrderStatusLog.__table__.columns
        assert "deleted_at" not in cols, "append-only model must not have deleted_at"


class TestOrderStatusLogBehavior:
    def test_repr_contains_ids_and_statuses(self) -> None:
        log = OrderStatusLog(
            **_valid_order_status_log_kwargs(
                from_status=OrderStatus.PENDING.value,
                to_status=OrderStatus.CONFIRMED.value,
            )
        )
        r = repr(log)
        assert str(log.id) in r
        assert str(log.order_id) in r
        assert "pending" in r
        assert "confirmed" in r

    def test_repr_does_not_expose_reason(self) -> None:
        """reason pode conter texto livre com dados sensíveis — não expor em repr."""
        log = OrderStatusLog(
            **_valid_order_status_log_kwargs(
                to_status=OrderStatus.CANCELED.value,
                reason="Cliente Maria desistiu porque endereço estava errado",
            )
        )
        r = repr(log)
        assert "Maria" not in r
        assert "endereço" not in r
        assert "desistiu" not in r

    def test_composes_created_at_mixin(self) -> None:
        """ADR-019: modelo append-only usa CreatedAtMixin (created_at NOT NULL)."""
        cols = OrderStatusLog.__table__.columns
        assert "created_at" in cols
        assert cols["created_at"].nullable is False

    def test_does_not_compose_timestamp_mixin(self) -> None:
        """Regressão ADR-019: TimestampMixin é mutuamente exclusivo com CreatedAtMixin."""
        cols = OrderStatusLog.__table__.columns
        assert "updated_at" not in cols, (
            "OrderStatusLog must not compose TimestampMixin (append-only)"
        )

    def test_does_not_compose_soft_delete_mixin(self) -> None:
        """Regressão ADR-019: SoftDeleteMixin não faz sentido em log append-only."""
        cols = OrderStatusLog.__table__.columns
        assert "deleted_at" not in cols, (
            "OrderStatusLog must not compose SoftDeleteMixin (append-only)"
        )


class TestOrderStatusLogCheckDynamic:
    """Regressão ADR-006 + ADR-019: CHECKs reconstruídos do StrEnum OrderStatus."""

    def test_from_status_check_allows_null(self) -> None:
        """ADR-019: from_status=NULL significa 'criação do pedido'.

        Sem o prefixo 'IS NULL OR' a primeira inserção do log quebra no banco.
        Armadilha não-óbvia: enums dos 10 modelos anteriores são todos NOT NULL.
        """
        assert _FROM_STATUS_CHECK.startswith("from_status IS NULL OR")

    def test_from_status_check_contains_all_enum_values(self) -> None:
        """Se OrderStatus ganhar valor novo, CHECK precisa acompanhar."""
        for status in OrderStatus:
            assert f"'{status.value}'" in _FROM_STATUS_CHECK

    def test_to_status_check_is_not_null(self) -> None:
        """ADR-019: to_status é NOT NULL — toda transição tem destino."""
        assert "IS NULL" not in _TO_STATUS_CHECK

    def test_to_status_check_contains_all_enum_values(self) -> None:
        """Se OrderStatus ganhar valor novo, CHECK precisa acompanhar."""
        for status in OrderStatus:
            assert f"'{status.value}'" in _TO_STATUS_CHECK
