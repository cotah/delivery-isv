"""Testes do serviço verify_otp (ADR-025)."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth.jwt import decode_access_token
from app.services.auth.otp import (
    INVALID_OTP_MESSAGE,
    MAX_OTP_ATTEMPTS,
    InvalidOtpError,
    verify_otp,
)


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class TestVerifyOtpHappyPath:
    def test_success_returns_user_and_token(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        otp_code_factory(phone=phone, code_hash=_hash(code))

        user, token = verify_otp(session=db_session, phone=phone, code=code)

        assert isinstance(user, User)
        assert user.phone == phone
        assert isinstance(token, str)
        assert len(token) > 0

    def test_creates_new_user_when_phone_unknown(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        otp_code_factory(phone=phone, code_hash=_hash(code))

        # Phone não existe em users antes
        before = db_session.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
        assert before is None

        user, _ = verify_otp(session=db_session, phone=phone, code=code)

        after = db_session.execute(select(User).where(User.phone == phone)).scalar_one()
        assert after.id == user.id

    def test_reuses_existing_user_when_phone_exists(
        self,
        db_session: Session,
        user_factory: Any,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        existing = user_factory(phone=phone)
        otp_code_factory(phone=phone, code_hash=_hash(code))

        user, _ = verify_otp(session=db_session, phone=phone, code=code)

        assert user.id == existing.id

    def test_marks_otp_as_consumed_on_success(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        otp = otp_code_factory(phone=phone, code_hash=_hash(code))

        verify_otp(session=db_session, phone=phone, code=code)

        db_session.refresh(otp)
        assert otp.consumed_at is not None

    def test_returns_valid_jwt_with_correct_claims(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        otp_code_factory(phone=phone, code_hash=_hash(code))

        user, token = verify_otp(session=db_session, phone=phone, code=code)

        payload = decode_access_token(token)
        assert payload.user_id == user.id
        assert payload.phone == phone
        assert payload.token_type == "access"


class TestVerifyOtpErrors:
    def test_raises_invalid_when_no_active_otp(
        self,
        db_session: Session,
    ) -> None:
        with pytest.raises(InvalidOtpError, match="inválido, expirado"):
            verify_otp(session=db_session, phone="+5531999887766", code="123456")

    def test_raises_invalid_when_otp_expired(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        past = datetime.now(UTC) - timedelta(minutes=1)
        otp_code_factory(phone=phone, code_hash=_hash(code), expires_at=past)

        with pytest.raises(InvalidOtpError):
            verify_otp(session=db_session, phone=phone, code=code)

    def test_raises_invalid_when_otp_already_consumed(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        otp_code_factory(
            phone=phone,
            code_hash=_hash(code),
            consumed_at=datetime.now(UTC) - timedelta(minutes=1),
        )

        with pytest.raises(InvalidOtpError):
            verify_otp(session=db_session, phone=phone, code=code)

    def test_raises_invalid_when_hash_does_not_match(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        otp_code_factory(phone=phone, code_hash=_hash("123456"))

        with pytest.raises(InvalidOtpError):
            verify_otp(session=db_session, phone=phone, code="000000")

    def test_raises_invalid_when_attempts_exhausted(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        """Após MAX_OTP_ATTEMPTS tentativas erradas, OTP fica permanentemente inválido."""
        phone = "+5531999887766"
        otp_code_factory(phone=phone, code_hash=_hash("123456"))

        # 3 tentativas erradas: cada uma incrementa attempts
        for _ in range(MAX_OTP_ATTEMPTS):
            with pytest.raises(InvalidOtpError):
                verify_otp(session=db_session, phone=phone, code="000000")

        # 4ª tentativa (mesmo com código certo) — attempts > MAX, bloqueado
        with pytest.raises(InvalidOtpError):
            verify_otp(session=db_session, phone=phone, code="123456")

    def test_attempts_incremented_on_wrong_code(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        otp = otp_code_factory(phone=phone, code_hash=_hash("123456"))
        assert otp.attempts == 0

        with pytest.raises(InvalidOtpError):
            verify_otp(session=db_session, phone=phone, code="000000")

        db_session.refresh(otp)
        assert otp.attempts == 1

    def test_attempts_exhausted_marks_otp_consumed(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        otp = otp_code_factory(phone=phone, code_hash=_hash("123456"))

        # Esgotar attempts (3 erros)
        for _ in range(MAX_OTP_ATTEMPTS):
            with pytest.raises(InvalidOtpError):
                verify_otp(session=db_session, phone=phone, code="000000")

        # 4ª: bloqueia + marca consumed
        with pytest.raises(InvalidOtpError):
            verify_otp(session=db_session, phone=phone, code="123456")

        db_session.refresh(otp)
        assert otp.consumed_at is not None

    def test_all_error_messages_identical(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        """Anti-enumeração: todas as 5 falhas têm mesma string externa.

        Cobre os 5 cenários documentados em INVALID_OTP_MESSAGE:
        not_found, hash errado, expired, consumed, attempts esgotados.
        """
        # Cenário 1: not_found (phone sem OTP ativo)
        with pytest.raises(InvalidOtpError) as e1:
            verify_otp(session=db_session, phone="+5531999887766", code="123456")
        assert str(e1.value) == INVALID_OTP_MESSAGE

        # Cenário 2: hash errado
        otp_code_factory(phone="+5531988776655", code_hash=_hash("123456"))
        with pytest.raises(InvalidOtpError) as e2:
            verify_otp(session=db_session, phone="+5531988776655", code="000000")
        assert str(e2.value) == INVALID_OTP_MESSAGE

        # Cenário 3: expired
        otp_code_factory(
            phone="+5511999887766",
            code_hash=_hash("123456"),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        with pytest.raises(InvalidOtpError) as e3:
            verify_otp(session=db_session, phone="+5511999887766", code="123456")
        assert str(e3.value) == INVALID_OTP_MESSAGE

        # Cenário 4: consumed (OTP já foi usado)
        otp_code_factory(
            phone="+5521999887766",
            code_hash=_hash("123456"),
            consumed_at=datetime.now(UTC),
        )
        with pytest.raises(InvalidOtpError) as e4:
            verify_otp(session=db_session, phone="+5521999887766", code="123456")
        assert str(e4.value) == INVALID_OTP_MESSAGE

        # Cenário 5: attempts esgotados (já em MAX, próxima tentativa bloqueia)
        otp_code_factory(
            phone="+5541999887766",
            code_hash=_hash("123456"),
            attempts=3,
        )
        with pytest.raises(InvalidOtpError) as e5:
            verify_otp(session=db_session, phone="+5541999887766", code="000000")
        assert str(e5.value) == INVALID_OTP_MESSAGE

        # Consistência absoluta: 5 mensagens literalmente idênticas
        assert (
            str(e1.value)
            == str(e2.value)
            == str(e3.value)
            == str(e4.value)
            == str(e5.value)
            == INVALID_OTP_MESSAGE
        )
