"""Interface abstrata para providers SMS (ADR-025).

Define contrato que qualquer provider (mock, Zenvia, Twilio) tem que cumprir.
Mock implementation em mock.py. Real providers virão em ciclo futuro
quando CNPJ for ativado.

MAGIC_FAILURE_PHONE: número reservado pra testar cenário de falha sem
configurar provider real. DDD 00 é impossível no Brasil (DDDs reais
começam em 11). Pattern Twilio/Stripe de magic numbers.
"""

from dataclasses import dataclass
from typing import Protocol

MAGIC_FAILURE_PHONE = "+5500000000000"


class SMSProviderError(Exception):
    """Base para erros de provider SMS."""


class SMSProviderConfigError(SMSProviderError):
    """Configuração inválida do provider (API key ausente, URL errada).

    Levantada no __init__ do provider. App não deve subir se isso
    acontecer em startup — fail-fast.
    """


class SMSSendError(SMSProviderError):
    """Falha no envio do SMS (timeout, 5xx do provider, rejeitado).

    Levantada no send_otp em runtime. No endpoint, vira HTTP 500
    (erro do servidor, não do cliente).
    """


@dataclass(frozen=True)
class SendResult:
    """Resultado de um envio de SMS bem-sucedido.

    Campos:
    - message_id: identificador retornado pelo provider (mock usa UUID fake).
                  Útil pra rastreabilidade futura (webhook de status de entrega).
    - provider: nome do provider que enviou ("mock", "zenvia", etc.).
                Útil pra debug e auditoria.
    """

    message_id: str
    provider: str


class SMSProvider(Protocol):
    """Protocol para providers SMS.

    Implementações:
    - MockSMSProvider (app/services/sms/mock.py) — desenvolvimento
    - ZenviaSMSProvider (futuro) — produção quando CNPJ ativar

    Método único send_otp recebe phone E.164 + código de 6 dígitos e
    retorna SendResult. Levanta SMSSendError em falha.
    """

    def send_otp(self, phone: str, code: str) -> SendResult:
        """Envia OTP pro phone. Raises SMSSendError em falha."""
        ...
