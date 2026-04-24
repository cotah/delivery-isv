"""Mock SMSProvider pra desenvolvimento (ADR-025).

Loga código OTP via logging padrão em vez de enviar SMS real.
Dev consegue ler código no terminal e colar no app durante testes.

FAIL-FAST EM PRODUÇÃO: se APP_ENV=production, MockSMSProvider recusa
instanciar. Protege contra config errada acidental que vazaria OTPs
reais em logs de observability (CloudWatch, Datadog, Sentry).

MAGIC_FAILURE_PHONE: se send_otp for chamado com esse phone,
simula SMSSendError. Útil pra testar fluxo de erro sem provider real.
"""

import logging
import uuid

from app.services.sms.base import (
    MAGIC_FAILURE_PHONE,
    SendResult,
    SMSProviderConfigError,
    SMSSendError,
)
from app.utils.validators import mask_phone_for_log

logger = logging.getLogger(__name__)


class MockSMSProvider:
    """Provider mock pra desenvolvimento local e testes.

    NUNCA usar em produção — protege via fail-fast no __init__.
    """

    provider_name = "mock"

    def __init__(self, app_env: str) -> None:
        """Inicializa mock. Falha se app_env=='production'.

        Args:
            app_env: valor de APP_ENV ("local", "staging", "production").

        Raises:
            SMSProviderConfigError: se app_env for "production".
        """
        if app_env == "production":
            raise SMSProviderConfigError(
                "MockSMSProvider cannot be used in production. "
                "Set SMS_PROVIDER to a real provider when APP_ENV=production."
            )
        self._app_env = app_env

    def send_otp(self, phone: str, code: str) -> SendResult:
        """Simula envio de OTP via log estruturado.

        Magic number: se phone == MAGIC_FAILURE_PHONE, levanta SMSSendError
        (útil pra testar fluxo de erro).

        Retorna SendResult com message_id fake (UUID) e provider="mock".
        """
        if phone == MAGIC_FAILURE_PHONE:
            raise SMSSendError(f"Simulated failure for magic phone {MAGIC_FAILURE_PHONE}")

        message_id = f"mock-{uuid.uuid4()}"

        logger.info(
            "mock_sms.send_otp phone=%s code=%s message_id=%s provider=%s",
            mask_phone_for_log(phone),
            code,
            message_id,
            self.provider_name,
        )

        return SendResult(message_id=message_id, provider=self.provider_name)
