"""Testes do MockSMSProvider (ADR-025)."""

import logging

import pytest

from app.services.sms.base import (
    MAGIC_FAILURE_PHONE,
    SendResult,
    SMSProviderConfigError,
    SMSSendError,
)
from app.services.sms.mock import MockSMSProvider


class TestMockSMSProvider:
    def test_mock_sends_valid_phone(self) -> None:
        provider = MockSMSProvider(app_env="local")
        result = provider.send_otp("+5531999887766", "123456")

        assert isinstance(result, SendResult)
        assert result.provider == "mock"
        assert result.message_id.startswith("mock-")

    def test_mock_message_id_is_unique_per_call(self) -> None:
        provider = MockSMSProvider(app_env="local")
        r1 = provider.send_otp("+5531999887766", "111111")
        r2 = provider.send_otp("+5531999887766", "222222")

        assert r1.message_id != r2.message_id

    def test_mock_magic_phone_raises_sms_send_error(self) -> None:
        provider = MockSMSProvider(app_env="local")
        with pytest.raises(SMSSendError, match="Simulated failure"):
            provider.send_otp(MAGIC_FAILURE_PHONE, "123456")

    def test_mock_refuses_production_env(self) -> None:
        with pytest.raises(SMSProviderConfigError, match="cannot be used in production"):
            MockSMSProvider(app_env="production")

    def test_mock_accepts_local_env(self) -> None:
        # No raise = accepted
        MockSMSProvider(app_env="local")

    def test_mock_accepts_staging_env(self) -> None:
        MockSMSProvider(app_env="staging")

    def test_mock_logs_masked_phone(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Phone deve aparecer mascarado em logs — PII protegida (ADR-010)."""
        provider = MockSMSProvider(app_env="local")
        phone = "+5531999887766"
        with caplog.at_level(logging.INFO, logger="app.services.sms.mock"):
            provider.send_otp(phone, "123456")

        # Phone cru nunca deve vazar
        assert phone not in caplog.text
        # Versão mascarada (mask_phone_for_log: +55*********66) deve estar presente
        assert "+55*********66" in caplog.text

    def test_mock_logs_code_in_dev(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Código OTP aparece no log em dev pra permitir copiar no app."""
        provider = MockSMSProvider(app_env="local")
        with caplog.at_level(logging.INFO, logger="app.services.sms.mock"):
            provider.send_otp("+5531999887766", "654321")

        assert "654321" in caplog.text
