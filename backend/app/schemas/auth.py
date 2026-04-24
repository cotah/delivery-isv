"""Schemas de autenticação (ADR-025).

Primeiro schema a usar field_validator chamando função canônica de
app.utils.validators — defense-in-depth ADR-010 na borda HTTP.
"""

from pydantic import BaseModel, Field, field_validator

from app.utils.validators import validate_phone_e164


class RequestOtpRequest(BaseModel):
    """Payload para POST /api/v1/auth/request-otp (ADR-025)."""

    phone: str = Field(
        ...,
        examples=["+5531999887766"],
        description=(
            "Telefone em formato E.164. Conversão de máscara local -> E.164 no frontend (ADR-009)."
        ),
    )

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str) -> str:
        return validate_phone_e164(value)


class RequestOtpResponse(BaseModel):
    """Resposta de POST /api/v1/auth/request-otp (ADR-025)."""

    message: str = Field(
        ...,
        examples=["Código enviado para +55 31 9*****7766"],
        description=("Mensagem humana confirmando envio do OTP, com phone parcialmente mascarado."),
    )
    expires_in_seconds: int = Field(
        default=600,
        examples=[600],
        description="Segundos até expiração do código (ADR-025 decisão 4: 10 minutos).",
    )
