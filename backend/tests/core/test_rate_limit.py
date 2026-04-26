"""Testes de app/core/rate_limit.py — fail-open inicialização + runtime."""

import logging
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core import rate_limit
from app.core.rate_limit import check_phone_rate_limit, limiter


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


class TestCheckPhoneRateLimit:
    """Helper `check_phone_rate_limit` — segunda camada de defesa.

    Manual hit em `limiter.limiter.hit()` (slowapi internals) bypassa
    o `_check_request_limit` → fail-open precisa ser replicado aqui
    (sem isso, queda do Redis volta a virar 500, regredindo MEDIUM #3).
    """

    def test_raises_rate_limit_exceeded_when_limit_hit(self) -> None:
        """4ª chamada com limit `3/hour` raise RateLimitExceeded.

        Pattern análogo aos testes IP-based em test_auth.py — fixture
        autouse `_reset_rate_limiter` zera contadores entre testes.
        """
        phone = "+5533999990010"

        for _ in range(3):
            check_phone_rate_limit(scope="unit-test", phone=phone, limit_str="3/hour")

        with pytest.raises(RateLimitExceeded):
            check_phone_rate_limit(scope="unit-test", phone=phone, limit_str="3/hour")

    def test_fail_open_when_storage_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Storage `.hit()` raise → swallow + WARNING log (sem propagar).

        Slowapi `swallow_errors=True` cobre `_check_request_limit` interno,
        NÃO cobre hit manual via `limiter.limiter.hit`. Helper replica
        pattern fail-open (ADR-022 + CP3c Auth D2).
        """

        def raise_redis_error(*args: Any, **kwargs: Any) -> bool:
            raise RedisError("simulated runtime outage")

        monkeypatch.setattr(limiter.limiter, "hit", raise_redis_error)

        with caplog.at_level(logging.WARNING, logger="app.core.rate_limit"):
            # Não deve raise — fail-open.
            check_phone_rate_limit(
                scope="unit-test",
                phone="+5533999990011",
                limit_str="3/hour",
            )

        assert "phone_rate_limit.storage_unreachable" in caplog.text
        assert "scope=unit-test" in caplog.text

    def test_noop_when_rate_limit_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """RATE_LIMIT_ENABLED=False (limiter.enabled=False) → no-op total.

        Espelha comportamento do decorator `@limiter.limit` quando
        slowapi `enabled=False` (E5 — Limiter inerte).
        """
        monkeypatch.setattr(limiter, "enabled", False)
        phone = "+5533999990012"

        # Bem além do limit — não deve raise nem incrementar storage.
        for _ in range(50):
            check_phone_rate_limit(scope="unit-test", phone=phone, limit_str="3/hour")

    def test_namespace_separates_scopes(self) -> None:
        """Mesmo phone em scopes diferentes — contadores independentes.

        Identifiers `(f"phone:{scope}", phone)` namespeiam keys Redis
        por scope. request-otp e verify-otp não compartilham contador
        para o mesmo phone (E4).
        """
        phone = "+5533999990013"

        # Esgota scope-a (limit 2/hour).
        for _ in range(2):
            check_phone_rate_limit(scope="scope-a", phone=phone, limit_str="2/hour")

        # 3ª chamada em scope-a raise.
        with pytest.raises(RateLimitExceeded):
            check_phone_rate_limit(scope="scope-a", phone=phone, limit_str="2/hour")

        # scope-b com mesmo phone deve ter contador independente.
        for _ in range(2):
            check_phone_rate_limit(scope="scope-b", phone=phone, limit_str="2/hour")
