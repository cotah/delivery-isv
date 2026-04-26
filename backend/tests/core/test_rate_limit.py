"""Testes de app/core/rate_limit.py — fail-open inicialização + runtime."""

import logging
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core import rate_limit
from app.core.rate_limit import limiter


class TestBuildLimiterFailOpen:
    def test_build_limiter_fails_open_when_limiter_init_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Se Limiter() com storage_uri levantar, fallback pra Limiter in-memory.

        Pattern fail-open (ADR-025 decisão 8 + D4 do CP3c): app NÃO trava
        quando Redis indisponível na inicialização. Slowapi atual usa lazy
        connect (não levanta na instanciação), mas try/except é defensivo
        contra mudanças futuras do comportamento.
        """
        call_count = [0]

        def fake_limiter(*args: Any, **kwargs: Any) -> Limiter:
            call_count[0] += 1
            # 1ª chamada (com storage_uri) levanta — simula Redis init failure.
            # 2ª chamada (sem storage, in-memory fallback) retorna Limiter real.
            if call_count[0] == 1:
                raise ConnectionError("redis unreachable")
            return Limiter(key_func=get_remote_address)

        monkeypatch.setattr(rate_limit, "Limiter", fake_limiter)

        with caplog.at_level(logging.WARNING, logger="app.core.rate_limit"):
            result = rate_limit._build_limiter()

        assert result is not None
        assert "rate_limit.redis_init_failed" in caplog.text
        assert "fallback=memory_only" in caplog.text
        assert call_count[0] == 2


class TestRuntimeFailOpen:
    """Runtime fail-open: Redis cai DEPOIS do app subir.

    Cobre flags slowapi `swallow_errors=True` + `in_memory_fallback_enabled=True`
    em `_build_limiter()`. Quando `_storage.incr()` raise `RedisError` no
    primeiro hit, slowapi transiciona pra in-memory transparente — request
    HTTP segue ≠ 500 (ADR-022 + CP3c Auth D2).
    """

    @pytest.fixture(autouse=True)
    def _reset_storage_dead(self) -> Generator[None, None, None]:
        # slowapi marca _storage_dead=True ao transicionar — limpar entre
        # testes pra não vazar estado (limiter.reset() não cobre esse flag).
        limiter._storage_dead = False
        yield
        limiter._storage_dead = False

    def test_runtime_fail_open_when_storage_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
    ) -> None:
        """Storage Redis raise no .incr() → request retorna ≠ 500.

        Antes do fix: 500 Internal Server Error plain text (exception
        propaga do redis.connection através do slowapi sem handler).
        Depois do fix: slowapi swallow + in-memory fallback → request
        chega no endpoint → 200 OK (MockSMSProvider responde).
        """

        def raise_redis_error(*args: Any, **kwargs: Any) -> int:
            raise RedisError("simulated runtime outage")

        monkeypatch.setattr(limiter._storage, "incr", raise_redis_error)

        resp = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+5533999990001"},
        )

        # O fundamental: != 500. 200 esperado (phone normal + Mock SMS).
        assert resp.status_code != 500
        assert resp.status_code == 200
        # Body em formato JSON (ADR-022), não plain text "Internal Server Error".
        assert resp.headers.get("content-type", "").startswith("application/json")

    def test_runtime_fail_open_logs_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Slowapi loga WARNING `Rate limit storage unreachable` na transição.

        Mensagem propaga via logger 'slowapi' (BlackHoleHandler local +
        propagate=True → root). Ops captura via Sentry/Datadog quando
        observability entrar (débito futuro).
        """

        def raise_redis_error(*args: Any, **kwargs: Any) -> int:
            raise RedisError("simulated runtime outage")

        monkeypatch.setattr(limiter._storage, "incr", raise_redis_error)

        with caplog.at_level(logging.WARNING, logger="slowapi"):
            client.post(
                "/api/v1/auth/request-otp",
                json={"phone": "+5533999990001"},
            )

        # Mensagem canônica do slowapi (extension.py:635-637).
        assert "Rate limit storage unreachable" in caplog.text
