"""Testes das dependencies do FastAPI (ADR-020 layer: api)."""

import pytest

from app.api.deps import get_sms_provider
from app.core.config import get_settings
from app.services.sms.base import SMSProviderConfigError
from app.services.sms.mock import MockSMSProvider


class TestGetSmsProvider:
    def setup_method(self) -> None:
        # Invalida caches entre casos (get_settings + get_sms_provider)
        get_settings.cache_clear()
        get_sms_provider.cache_clear()

    def teardown_method(self) -> None:
        get_settings.cache_clear()
        get_sms_provider.cache_clear()

    def test_returns_mock_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMS_PROVIDER", "mock")
        monkeypatch.setenv("APP_ENV", "local")

        provider = get_sms_provider()

        assert isinstance(provider, MockSMSProvider)

    def test_raises_on_unknown_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMS_PROVIDER", "foobar")

        with pytest.raises(SMSProviderConfigError, match="Unknown SMS_PROVIDER"):
            get_sms_provider()

    def test_is_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMS_PROVIDER", "mock")
        monkeypatch.setenv("APP_ENV", "local")

        p1 = get_sms_provider()
        p2 = get_sms_provider()

        assert p1 is p2
