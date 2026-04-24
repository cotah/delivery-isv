"""Serviço de OTP — request-otp (ADR-020 layer: service, ADR-025)."""

import hashlib
import logging
import secrets

from sqlalchemy.orm import Session

from app.repositories import otp as otp_repository
from app.services.sms.base import SMSProvider, SMSSendError
from app.utils.validators import mask_phone_for_display

logger = logging.getLogger(__name__)

OTP_EXPIRATION_MINUTES = 10


class OtpRequestFailedError(Exception):
    """Falha ao solicitar OTP (problema no SMS provider).

    Route converte em HTTP 502 com code=sms_provider_error (ADR-022).
    """


def _generate_otp_code() -> str:
    """Gera código OTP de 6 dígitos zero-padded (ADR-025 decisão 3).

    Returns:
        String de 6 dígitos, ex: "472891", "000483".
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp_code(code: str) -> str:
    """sha256 hexdigest do código cru (ADR-025 decisão 3).

    Returns:
        64 chars hexdigest.
    """
    return hashlib.sha256(code.encode()).hexdigest()


def request_otp(
    session: Session,
    sms_provider: SMSProvider,
    phone: str,
) -> str:
    """Fluxo completo de request-otp: invalida antigos, cria novo, envia SMS.

    ADR-025 decisões 1, 3, 4 (hash, expiração, lazy User — User não tocado aqui).

    Pattern anti-stall: commit ANTES da chamada HTTP ao provider.
    Se provider falha, transação já fechou — conexão liberada.
    OtpCode fica no banco mas invalidado via consumed_at.

    Args:
        session: SQLAlchemy session
        sms_provider: SMSProvider injetado via Depends(get_sms_provider)
        phone: phone E.164 validado

    Returns:
        Phone mascarado para display (ex: "+55 31 9*****7766").

    Raises:
        OtpRequestFailedError: se SMS provider retornou erro.
    """
    invalidated = otp_repository.invalidate_active_otps(session, phone)
    if invalidated > 0:
        logger.info("request_otp.invalidated_previous count=%d", invalidated)

    code = _generate_otp_code()
    code_hash = _hash_otp_code(code)

    otp = otp_repository.create_otp_code(
        session=session,
        phone=phone,
        code_hash=code_hash,
        expires_in_minutes=OTP_EXPIRATION_MINUTES,
    )
    # Guardar id antes do commit: defensivo contra expire_on_commit=True futuro.
    # Config atual (session.py) é expire_on_commit=False — acesso post-commit
    # funciona sem reload — mas não remover esta linha.
    otp_id = otp.id

    # Commit antes da chamada HTTP externa: libera conexão DB enquanto
    # esperamos provider. Se provider falhar, OtpCode fica persistido
    # e é invalidado via nova transação abaixo.
    session.commit()

    try:
        sms_provider.send_otp(phone=phone, code=code)
    except SMSSendError as exc:
        otp_repository.mark_otp_consumed(session, otp_id)
        session.commit()
        logger.warning(
            "request_otp.sms_provider_failed phone=%s",
            mask_phone_for_display(phone),
        )
        raise OtpRequestFailedError(
            "Falha ao enviar SMS. Tente novamente em alguns segundos."
        ) from exc

    logger.info(
        "request_otp.success phone=%s otp_id=%s",
        mask_phone_for_display(phone),
        otp_id,
    )

    return mask_phone_for_display(phone)
