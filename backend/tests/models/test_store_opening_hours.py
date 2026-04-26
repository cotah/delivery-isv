"""Testes do model StoreOpeningHours (ADR-026 dec. 1, CP1b HIGH #1)."""

import uuid
from datetime import time
from typing import Any

import pytest
from sqlalchemy import CheckConstraint, Table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.store_opening_hours import StoreOpeningHours


class TestStoreOpeningHoursStructure:
    def test_has_correct_tablename(self) -> None:
        assert StoreOpeningHours.__tablename__ == "store_opening_hours"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = StoreOpeningHours.__table__.columns
        required = ("id", "store_id", "day_of_week", "open_time", "close_time")
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_timestamp_columns(self) -> None:
        cols = StoreOpeningHours.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            assert cols[col_name].nullable is False

    def test_has_no_soft_delete(self) -> None:
        """ADR-026 dec. — D2 do CP1b: sem SoftDeleteMixin (DELETE + CASCADE da Store)."""
        cols = StoreOpeningHours.__table__.columns
        assert "deleted_at" not in cols

    def test_has_fk_to_stores_with_cascade(self) -> None:
        """ADR-015: composição estrita — CASCADE de Store deleta slots."""
        table = StoreOpeningHours.__table__
        assert isinstance(table, Table)
        fks = list(table.columns["store_id"].foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "stores"
        assert fk.column.name == "id"
        assert fk.ondelete == "CASCADE"

    def test_has_check_day_of_week_valid_range(self) -> None:
        table = StoreOpeningHours.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        check = next(
            (c for c in checks if c.name == "ck_store_opening_hours_day_of_week_valid_range"),
            None,
        )
        assert check is not None, "ck_store_opening_hours_day_of_week_valid_range not found"
        sql_text = str(check.sqltext)
        assert "day_of_week" in sql_text
        assert ">= 0" in sql_text
        assert "<= 6" in sql_text

    def test_has_check_open_time_close_time_different(self) -> None:
        table = StoreOpeningHours.__table__
        assert isinstance(table, Table)
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        check = next(
            (
                c
                for c in checks
                if c.name == "ck_store_opening_hours_open_time_close_time_different"
            ),
            None,
        )
        assert check is not None
        sql_text = str(check.sqltext)
        assert "open_time" in sql_text
        assert "close_time" in sql_text

    def test_has_unique_constraint_composite(self) -> None:
        """UNIQUE (store_id, day_of_week, open_time) — protege duplicatas exatas."""
        table = StoreOpeningHours.__table__
        assert isinstance(table, Table)
        # UniqueConstraint com nome completo (CLAUDE.md armadilha #2).
        # Pode aparecer como Index unique=True OU UniqueConstraint dependendo da versão.
        ix = next(
            (
                i
                for i in table.indexes
                if i.name == "uq_store_opening_hours_store_id_day_of_week_open_time"
            ),
            None,
        )
        if ix is not None:
            assert ix.unique is True
        else:
            # Procura como Constraint
            from sqlalchemy import UniqueConstraint

            uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
            uq = next(
                (
                    u
                    for u in uniques
                    if u.name == "uq_store_opening_hours_store_id_day_of_week_open_time"
                ),
                None,
            )
            assert uq is not None, "UNIQUE constraint composta não encontrada"
            cols = [c.name for c in uq.columns]
            assert cols == ["store_id", "day_of_week", "open_time"]

    def test_has_index_composite_for_aberto_agora_query(self) -> None:
        """Index (store_id, day_of_week) acelera query 'aberto agora?'."""
        table = StoreOpeningHours.__table__
        assert isinstance(table, Table)
        ix = next(
            (i for i in table.indexes if i.name == "ix_store_opening_hours_store_id_day_of_week"),
            None,
        )
        assert ix is not None
        col_names = [c.name for c in ix.columns]
        assert col_names == ["store_id", "day_of_week"]


class TestStoreOpeningHoursBehavior:
    def test_repr_format(self) -> None:
        slot = StoreOpeningHours(
            id=uuid.uuid4(),
            store_id=uuid.uuid4(),
            day_of_week=1,
            open_time=time(11, 0),
            close_time=time(23, 0),
        )
        r = repr(slot)
        assert "StoreOpeningHours" in r
        assert "day=1" in r
        assert "11:00:00-23:00:00" in r

    def test_create_basic_slot(self, db_session: Session, store_factory: Any) -> None:
        store = store_factory()
        slot = StoreOpeningHours(
            store_id=store.id,
            day_of_week=1,
            open_time=time(11, 0),
            close_time=time(23, 0),
        )
        db_session.add(slot)
        db_session.flush()
        assert slot.id is not None
        assert slot.store_id == store.id
        assert slot.day_of_week == 1


class TestStoreOpeningHoursPostgresConstraints:
    """Constraints exercitadas no Postgres real (não só metadata)."""

    def test_day_of_week_below_zero_rejected(self, db_session: Session, store_factory: Any) -> None:
        store = store_factory()
        slot = StoreOpeningHours(
            store_id=store.id,
            day_of_week=-1,
            open_time=time(11, 0),
            close_time=time(23, 0),
        )
        db_session.add(slot)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_day_of_week_above_six_rejected(self, db_session: Session, store_factory: Any) -> None:
        store = store_factory()
        slot = StoreOpeningHours(
            store_id=store.id,
            day_of_week=7,
            open_time=time(11, 0),
            close_time=time(23, 0),
        )
        db_session.add(slot)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_open_time_equals_close_time_rejected(
        self, db_session: Session, store_factory: Any
    ) -> None:
        store = store_factory()
        slot = StoreOpeningHours(
            store_id=store.id,
            day_of_week=1,
            open_time=time(11, 0),
            close_time=time(11, 0),
        )
        db_session.add(slot)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_unique_constraint_rejects_duplicate_exact(
        self, db_session: Session, store_factory: Any
    ) -> None:
        """ADR-026 reforço D3: UNIQUE protege duplicatas exatas."""
        store = store_factory()
        slot_a = StoreOpeningHours(
            store_id=store.id,
            day_of_week=1,
            open_time=time(11, 0),
            close_time=time(14, 0),
        )
        slot_b = StoreOpeningHours(
            store_id=store.id,
            day_of_week=1,
            open_time=time(11, 0),
            close_time=time(15, 0),  # close diferente, mas UNIQUE eh em (store, day, open)
        )
        db_session.add(slot_a)
        db_session.flush()
        db_session.add(slot_b)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_unique_allows_overlap_partial(self, db_session: Session, store_factory: Any) -> None:
        """ADR-026 reforço D3: UNIQUE NÃO protege overlaps parciais.

        Documenta a nuance: slots sobrepostos com open_time diferente passam.
        Validacao de overlap eh deferida pro painel admin (debito ADR-026 D4).
        """
        store = store_factory()
        slot_a = StoreOpeningHours(
            store_id=store.id,
            day_of_week=1,
            open_time=time(11, 0),
            close_time=time(14, 0),
        )
        slot_b = StoreOpeningHours(
            store_id=store.id,
            day_of_week=1,
            open_time=time(11, 30),  # open diferente, sobrepõe A
            close_time=time(13, 0),
        )
        db_session.add_all([slot_a, slot_b])
        # Não deve estourar — overlap parcial passa.
        db_session.flush()
        assert slot_a.id is not None
        assert slot_b.id is not None

    def test_cascade_delete_when_store_deleted(
        self, db_session: Session, store_factory: Any
    ) -> None:
        """ADR-015 + ADR-026 dec. 1: DELETE CASCADE da Store remove slots.

        Usa DELETE SQL direto pra evitar cascade Python (Store.opening_hours
        é lazy='raise' — relationship do ORM não pode ser tocado sem eager load).
        DB-level CASCADE via FK ondelete='CASCADE' é o que está sendo testado.
        """
        from sqlalchemy import delete, select

        from app.models.store import Store

        store = store_factory()
        slot = StoreOpeningHours(
            store_id=store.id,
            day_of_week=1,
            open_time=time(11, 0),
            close_time=time(23, 0),
        )
        db_session.add(slot)
        db_session.flush()
        slot_id = slot.id
        store_id = store.id

        # Expira o objeto Store da sessão pra evitar que ORM tente relationship.
        db_session.expunge(store)
        db_session.execute(delete(Store).where(Store.id == store_id))
        db_session.flush()

        result = db_session.execute(
            select(StoreOpeningHours).where(StoreOpeningHours.id == slot_id)
        ).scalar_one_or_none()
        assert result is None, "CASCADE deveria ter deletado o slot junto"
