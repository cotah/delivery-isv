"""Testes do contrato de base.py (ADR-025)."""

from dataclasses import FrozenInstanceError

import pytest

from app.services.sms.base import (
    MAGIC_FAILURE_PHONE,
    SendResult,
    SMSProviderConfigError,
    SMSProviderError,
    SMSSendError,
)


class TestSendResult:
    def test_send_result_is_frozen(self) -> None:
        result = SendResult(message_id="mock-123", provider="mock")
        with pytest.raises(FrozenInstanceError):
            result.message_id = "mock-999"  # type: ignore[misc]

    def test_send_result_requires_fields(self) -> None:
        with pytest.raises(TypeError):
            SendResult()  # type: ignore[call-arg]


class TestMagicFailurePhone:
    def test_magic_failure_phone_is_invalid_ddd(self) -> None:
        """DDD 00 é impossível no Brasil — pattern magic number (Twilio/Stripe)."""
        assert MAGIC_FAILURE_PHONE.startswith("+5500")


class TestExceptionsHierarchy:
    def test_config_error_is_provider_error(self) -> None:
        assert issubclass(SMSProviderConfigError, SMSProviderError)

    def test_send_error_is_provider_error(self) -> None:
        assert issubclass(SMSSendError, SMSProviderError)
