"""Testes do helper is_store_open (ADR-026 dec. 1, 2, 3 + reforço D5)."""

import uuid
from datetime import UTC, datetime, time

import pytest

from app.models.store import Store
from app.models.store_opening_hours import StoreOpeningHours
from app.services.stores import SAO_PAULO_TZ, is_store_open, is_store_open_now


def _store_with_slots(slots: list[StoreOpeningHours]) -> Store:
    """Constrói Store em memória (sem flush) com opening_hours pré-populado.

    Útil pros testes do helper que não dependem de persistência.
    """
    store = Store(
        id=uuid.uuid4(),
        legal_name="Test LTDA",
        trade_name="Test",
        tax_id="11222333000181",
        tax_id_type="cnpj",
        slug="test-slug",
        category_id=uuid.uuid4(),
        city_id=uuid.uuid4(),
        street="Rua",
        number="1",
        neighborhood="Centro",
        zip_code="35855000",
        phone="+5531999887766",
    )
    store.opening_hours = slots
    return store


def _slot(day_of_week: int, open_time: time, close_time: time) -> StoreOpeningHours:
    return StoreOpeningHours(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        day_of_week=day_of_week,
        open_time=open_time,
        close_time=close_time,
    )


class TestIsStoreOpenGuard:
    """ADR-026 reforço D5: naive datetime levanta ValueError."""

    def test_naive_datetime_raises_value_error(self) -> None:
        store = _store_with_slots([])
        # 2026-04-27 segunda 12:00 sem timezone
        naive_dt = datetime(2026, 4, 27, 12, 0, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            is_store_open(store, naive_dt)


class TestIsStoreOpenRegularSlot:
    def test_open_during_regular_slot(self) -> None:
        # Segunda (DOW=1) 11:00-23:00, consultando às 14:00 SP
        store = _store_with_slots([_slot(1, time(11, 0), time(23, 0))])
        # Segunda 2026-04-27 14:00 em São Paulo
        dt = datetime(2026, 4, 27, 14, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is True

    def test_open_at_open_time_boundary(self) -> None:
        store = _store_with_slots([_slot(1, time(11, 0), time(23, 0))])
        dt = datetime(2026, 4, 27, 11, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is True

    def test_open_at_close_time_boundary(self) -> None:
        store = _store_with_slots([_slot(1, time(11, 0), time(23, 0))])
        dt = datetime(2026, 4, 27, 23, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is True

    def test_closed_outside_slot(self) -> None:
        store = _store_with_slots([_slot(1, time(11, 0), time(23, 0))])
        dt = datetime(2026, 4, 27, 9, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is False

    def test_closed_when_no_slots_for_day(self) -> None:
        # Slot só na segunda (DOW=1), consultando terça (DOW=2)
        store = _store_with_slots([_slot(1, time(11, 0), time(23, 0))])
        dt = datetime(2026, 4, 28, 14, 0, 0, tzinfo=SAO_PAULO_TZ)  # terça
        assert is_store_open(store, dt) is False

    def test_closed_when_no_slots_at_all(self) -> None:
        store = _store_with_slots([])
        dt = datetime(2026, 4, 27, 14, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is False


class TestIsStoreOpenCrossMidnight:
    """ADR-026 dec. 3: close_time < open_time = cruza meia-noite."""

    def test_open_during_cross_midnight_after_open(self) -> None:
        # Pizzaria segunda 18:00-02:00 (cruza pra terça)
        store = _store_with_slots([_slot(1, time(18, 0), time(2, 0))])
        # Segunda 19:00 — depois do open
        dt = datetime(2026, 4, 27, 19, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is True

    def test_open_during_cross_midnight_before_close(self) -> None:
        # Slot segunda 18:00-02:00 — checking 01:00 da manhã (terça?)
        # Mas a regra é "para CADA dia, slot DOW=N permite >=open OU <=close".
        # Então 01:00 na segunda: dt.dow=1, slot.dow=1 — passa pelo branch <=close.
        store = _store_with_slots([_slot(1, time(18, 0), time(2, 0))])
        dt = datetime(2026, 4, 27, 1, 0, 0, tzinfo=SAO_PAULO_TZ)  # segunda 01h
        assert is_store_open(store, dt) is True

    def test_closed_during_gap_in_cross_midnight(self) -> None:
        store = _store_with_slots([_slot(1, time(18, 0), time(2, 0))])
        # Segunda 03:00 — fora do slot
        dt = datetime(2026, 4, 27, 3, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is False

    def test_closed_during_gap_in_cross_midnight_morning(self) -> None:
        # Segunda 12:00 — antes do open=18 e depois do close=2
        store = _store_with_slots([_slot(1, time(18, 0), time(2, 0))])
        dt = datetime(2026, 4, 27, 12, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is False


class TestIsStoreOpenMultipleSlots:
    def test_open_in_multiple_slots_same_day(self) -> None:
        # Almoço 11-14 + jantar 18-23 na mesma segunda
        store = _store_with_slots(
            [
                _slot(1, time(11, 0), time(14, 0)),
                _slot(1, time(18, 0), time(23, 0)),
            ]
        )
        # Durante almoço
        dt_lunch = datetime(2026, 4, 27, 12, 30, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt_lunch) is True
        # Durante jantar
        dt_dinner = datetime(2026, 4, 27, 19, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt_dinner) is True
        # Entre almoço e jantar
        dt_gap = datetime(2026, 4, 27, 16, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt_gap) is False


class TestDOWConversion:
    """ADR-026 reforço D1: dt.isoweekday() % 7 mapeia pra Postgres DOW."""

    def test_segunda_python_isoweekday_1_dow_1(self) -> None:
        # 2026-04-27 é segunda. isoweekday=1 → DOW=1
        store = _store_with_slots([_slot(1, time(0, 0), time(23, 59))])
        dt = datetime(2026, 4, 27, 12, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is True

    def test_domingo_python_isoweekday_7_dow_0(self) -> None:
        # 2026-04-26 é domingo. isoweekday=7 → DOW=7%7=0
        store = _store_with_slots([_slot(0, time(0, 0), time(23, 59))])
        dt = datetime(2026, 4, 26, 12, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is True

    def test_sabado_python_isoweekday_6_dow_6(self) -> None:
        # 2026-05-02 é sábado. isoweekday=6 → DOW=6
        store = _store_with_slots([_slot(6, time(0, 0), time(23, 59))])
        dt = datetime(2026, 5, 2, 12, 0, 0, tzinfo=SAO_PAULO_TZ)
        assert is_store_open(store, dt) is True


class TestTimezoneConversion:
    """ADR-026 dec. 2: backend assume América/São_Paulo."""

    def test_utc_input_converted_to_sao_paulo(self) -> None:
        # Slot segunda 11:00-23:00 em São Paulo.
        store = _store_with_slots([_slot(1, time(11, 0), time(23, 0))])
        # 14:00 UTC = 11:00 São Paulo (UTC-3 sem horário de verão).
        # Se a conversão funcionar, deve estar aberto.
        dt_utc = datetime(2026, 4, 27, 14, 0, 0, tzinfo=UTC)
        assert is_store_open(store, dt_utc) is True

    def test_utc_before_sao_paulo_open_returns_false(self) -> None:
        store = _store_with_slots([_slot(1, time(11, 0), time(23, 0))])
        # 13:00 UTC = 10:00 São Paulo (antes do open=11:00).
        dt_utc = datetime(2026, 4, 27, 13, 0, 0, tzinfo=UTC)
        assert is_store_open(store, dt_utc) is False


class TestIsStoreOpenNowWrapper:
    def test_smoke_does_not_raise(self) -> None:
        """Wrapper de conveniência usa datetime.now(SAO_PAULO_TZ) — não estoura."""
        store = _store_with_slots([])  # Store em memória, sem flush
        result = is_store_open_now(store)
        assert isinstance(result, bool)
