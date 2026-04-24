"""Queries ORM de OtpCode (ADR-020 layer: repository, ADR-025)."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, update
from sqlalchemy.orm import Session

from app.models.otp_code import OtpCode


def invalidate_active_otps(session: Session, phone: str) -> int:
    """Invalida todos OTPs ativos (não consumidos) do phone.

    Seta consumed_at=now() em todos os OtpCode com:
    - phone matching
    - consumed_at IS NULL
    - expires_at > now (não expirados — expirados ficam como são, naturalmente inválidos)

    Usado antes de criar novo OtpCode no request-otp para garantir
    apenas 1 código ativo por phone (ADR-025 pattern iFood/Twilio).

    Args:
        session: SQLAlchemy session (caller gerencia commit)
        phone: phone E.164 validado

    Returns:
        Número de OtpCodes invalidados.
    """
    now = datetime.now(UTC)
    stmt = (
        update(OtpCode)
        .where(
            OtpCode.phone == phone,
            OtpCode.consumed_at.is_(None),
            OtpCode.expires_at > now,
        )
        .values(consumed_at=now)
    )
    # session.execute(update()) retorna CursorResult (tem rowcount).
    # Mypy tipa session.execute genérico como Result[Any] — cast pra honrar o
    # tipo real e acessar rowcount sem type: ignore.
    result = cast("CursorResult[Any]", session.execute(stmt))
    return result.rowcount


def create_otp_code(
    session: Session,
    phone: str,
    code_hash: str,
    expires_in_minutes: int = 10,
) -> OtpCode:
    """Cria novo OtpCode com expires_at = now + expires_in_minutes.

    Caller responsável por:
    - Ter invalidado OTPs ativos anteriores (invalidate_active_otps)
    - Hash do código (sha256 hex de 64 chars)
    - Commit da transação

    Args:
        session: SQLAlchemy session
        phone: phone E.164 validado
        code_hash: sha256 hexdigest do código cru (64 chars)
        expires_in_minutes: default 10 (ADR-025 decisão 4)

    Returns:
        OtpCode criado, com id atribuído após flush.
    """
    now = datetime.now(UTC)
    otp = OtpCode(
        phone=phone,
        code_hash=code_hash,
        expires_at=now + timedelta(minutes=expires_in_minutes),
        attempts=0,
    )
    session.add(otp)
    session.flush()
    return otp


def mark_otp_consumed(session: Session, otp_id: UUID) -> None:
    """Marca OtpCode como consumido (consumed_at=now).

    Usado em 2 cenários:
    1. Verify-otp bem-sucedido (CP3c)
    2. Invalidação manual após falha de SMS provider (CP3b)

    Usa UPDATE direto — não depende do objeto estar attached.
    Caller responsável pelo commit.

    Args:
        session: SQLAlchemy session
        otp_id: UUID do OtpCode a invalidar
    """
    now = datetime.now(UTC)
    stmt = update(OtpCode).where(OtpCode.id == otp_id).values(consumed_at=now)
    session.execute(stmt)
