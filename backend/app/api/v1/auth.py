"""Rotas HTTP de autenticação (ADR-020 layer: api, ADR-021 versioning, ADR-025)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_sms_provider
from app.api.errors import ErrorCode, ErrorResponse
from app.schemas.auth import RequestOtpRequest, RequestOtpResponse
from app.services.auth.otp import OTP_EXPIRATION_MINUTES, OtpRequestFailedError, request_otp
from app.services.sms.base import SMSProvider

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/request-otp",
    response_model=RequestOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Solicita código OTP por SMS",
    description=(
        "Envia código OTP de 6 dígitos por SMS para o telefone informado. "
        "Invalida qualquer código anterior ainda ativo. Código expira em 10 minutos. "
        "Endpoint público — autenticação não é necessária. "
        "Sem rate limit nesta versão (CP3b) — rate limit entra no CP3c. "
        "Se o provider SMS falhar, retorna 502 e nenhum código fica ativo."
    ),
    responses={
        422: {"model": ErrorResponse, "description": "Phone em formato inválido"},
        502: {"model": ErrorResponse, "description": "Provider SMS indisponível"},
    },
)
def request_otp_endpoint(
    payload: RequestOtpRequest,
    session: Annotated[Session, Depends(get_db_session)],
    sms_provider: Annotated[SMSProvider, Depends(get_sms_provider)],
) -> RequestOtpResponse:
    try:
        masked_phone = request_otp(
            session=session,
            sms_provider=sms_provider,
            phone=payload.phone,
        )
    except OtpRequestFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": ErrorCode.SMS_PROVIDER_ERROR.value,
                "message": str(exc),
            },
        ) from exc

    return RequestOtpResponse(
        message=f"Código enviado para {masked_phone}",
        expires_in_seconds=OTP_EXPIRATION_MINUTES * 60,
    )
