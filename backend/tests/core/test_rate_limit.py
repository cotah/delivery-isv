"""Testes de app/core/rate_limit.py — fail-open na inicialização."""

import logging
from typing import Any

import pytest
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core import rate_limit


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
