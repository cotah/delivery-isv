"""Serviço de OTP — request-otp + verify-otp (ADR-020 layer: service, ADR-025)."""

import hashlib
import hmac
import logging
import secrets

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import otp as otp_repository
from app.repositories import user as user_repository
from app.services.auth.jwt import create_access_token
from app.services.sms.base import SMSProvider, SMSSendError
from app.utils.validators import mask_phone_for_display, mask_phone_for_log

logger = logging.getLogger(__name__)

OTP_EXPIRATION_MINUTES = 10
MAX_OTP_ATTEMPTS = 3

# Mensagem ÚNICA para todos os 5 cenários de falha em verify-otp
# (anti-enumeração, ADR-025 decisão 5 + D8 do CP3c). Não diferenciar
# externamente: hash errado, expirado, consumed, attempts esgotados,
# OTP não encontrado — todos retornam mesma string.
INVALID_OTP_MESSAGE = "Código inválido, expirado ou já utilizado."


class OtpRequestFailedError(Exception):
    """Falha ao solicitar OTP (problema no SMS provider).

    Route converte em HTTP 502 com code=sms_provider_error (ADR-022).
    """


class InvalidOtpError(Exception):
    """Falha genérica em verify-otp.

    Route converte em HTTP 400 com code=invalid_otp_code + INVALID_OTP_MESSAGE.
    Anti-enumeração: cobre 5 cenários (hash errado, expirado, consumed,
    attempts esgotados, not_found) com mesma resposta externa.
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


def verify_otp(
    session: Session,
    phone: str,
    code: str,
) -> tuple[User, str]:
    """Fluxo completo de verify-otp: busca OTP, valida, cria/busca User, emite JWT.

    ADR-025 decisões 2, 3, 5, 6, 7.

    Ordem de operações (crítica pra segurança):
    1. SELECT FOR UPDATE no OtpCode ativo do phone — lock de linha
    2. Incrementar attempts ANTES de validar hash (anti brute force)
    3. Se attempts > MAX_OTP_ATTEMPTS: marcar consumed, raise
    4. Validar hash via hmac.compare_digest (constant-time — anti timing attack)
    5. Marcar OtpCode como consumed (anti-replay)
    6. find_or_create_user (lazy creation, ADR-025 decisão 6)
    7. session.commit() — único commit do fluxo (todos UPDATEs juntos)
    8. create_access_token

    Anti-enumeração: 5 cenários de erro (not_found, attempts esgotados,
    hash errado) viram MESMO InvalidOtpError com INVALID_OTP_MESSAGE.
    Logs internos diferenciam pra debug, response externa é uniforme.

    Args:
        session: SQLAlchemy session (em transação aberta — caller wrap)
        phone: phone E.164 validado (Pydantic)
        code: 6 dígitos (Pydantic)

    Returns:
        Tupla (User, access_token_jwt).

    Raises:
        InvalidOtpError: cobre todos os 5 cenários com mesma mensagem.
    """
    otp = otp_repository.find_active_otp_for_phone_for_update(session, phone)
    if otp is None:
        # Cenário 1 (not_found / expired / already_consumed): nada ativo encontrado.
        logger.info("verify_otp.not_found phone=%s", mask_phone_for_log(phone))
        raise InvalidOtpError(INVALID_OTP_MESSAGE)

    # Increment ANTES de validar hash — protege contra brute force
    # (mesmo se hash falhar, attempts persiste no commit final).
    otp_repository.increment_otp_attempts(session, otp.id)
    session.flush()
    session.refresh(otp)

    # Cenário 2 (attempts): excedeu MAX — invalidar permanentemente
    if otp.attempts > MAX_OTP_ATTEMPTS:
        otp_repository.mark_otp_consumed(session, otp.id)
        session.commit()
        logger.warning(
            "verify_otp.attempts_exhausted phone=%s attempts=%d",
            mask_phone_for_log(phone),
            otp.attempts,
        )
        raise InvalidOtpError(INVALID_OTP_MESSAGE)

    # Cenário 3 (hash): comparar com constant-time (anti timing attack)
    expected_hash = _hash_otp_code(code)
    if not hmac.compare_digest(otp.code_hash, expected_hash):
        # Persistir o increment de attempts mesmo em falha de hash.
        session.commit()
        logger.info(
            "verify_otp.invalid_hash phone=%s attempts=%d",
            mask_phone_for_log(phone),
            otp.attempts,
        )
        raise InvalidOtpError(INVALID_OTP_MESSAGE)

    # Hash bate — marcar consumed (anti-replay) e criar/buscar User
    otp_repository.mark_otp_consumed(session, otp.id)
    user = user_repository.find_or_create_user(session, phone)

    # Único commit do fluxo: todos os UPDATEs juntos. Lock FOR UPDATE
    # liberado aqui — outros requests verify-otp do mesmo phone destrancam.
    session.commit()

    token = create_access_token(user_id=user.id, phone=phone)

    logger.info(
        "verify_otp.success phone=%s user_id=%s",
        mask_phone_for_log(phone),
        user.id,
    )

    return user, token
