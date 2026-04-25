"""Rotas HTTP de autenticação (ADR-020 layer: api, ADR-021 versioning, ADR-025)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_sms_provider
from app.api.errors import ErrorCode, ErrorResponse
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.auth import (
    RequestOtpRequest,
    RequestOtpResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.services.auth.otp import (
    OTP_EXPIRATION_MINUTES,
    InvalidOtpError,
    OtpRequestFailedError,
    request_otp,
    verify_otp,
)
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
        "Rate limit por IP via slowapi+Redis (ADR-025 decisão 8). "
        "Se o provider SMS falhar, retorna 502 e nenhum código fica ativo."
    ),
    responses={
        422: {"model": ErrorResponse, "description": "Phone em formato inválido"},
        429: {"model": ErrorResponse, "description": "Rate limit excedido"},
        502: {"model": ErrorResponse, "description": "Provider SMS indisponível"},
    },
)
@limiter.limit(lambda: get_settings().RATE_LIMIT_REQUEST_OTP_IP)
def request_otp_endpoint(
    request: Request,
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


@router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Verifica código OTP e retorna JWT",
    description=(
        "Valida código OTP previamente solicitado via /auth/request-otp. "
        "Se válido: cria User (primeira vez) ou recupera existente, retorna JWT. "
        "Código expira após 3 tentativas erradas (anti brute force). "
        "Resposta 400 genérica para qualquer falha (anti-enumeração, ADR-025). "
        "Rate limit por IP via slowapi+Redis (ADR-025 decisão 8)."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Código inválido, expirado ou esgotou tentativas",
        },
        422: {"model": ErrorResponse, "description": "Phone ou code em formato inválido"},
        429: {"model": ErrorResponse, "description": "Rate limit excedido"},
    },
)
@limiter.limit(lambda: get_settings().RATE_LIMIT_VERIFY_OTP_IP)
def verify_otp_endpoint(
    request: Request,
    payload: VerifyOtpRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> VerifyOtpResponse:
    try:
        _user, access_token = verify_otp(
            session=session,
            phone=payload.phone,
            code=payload.code,
        )
    except InvalidOtpError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_OTP_CODE.value,
                "message": str(exc),
            },
        ) from exc

    settings = get_settings()
    return VerifyOtpResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=settings.JWT_EXPIRATION_MINUTES * 60,
    )
