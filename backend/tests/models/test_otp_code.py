"""Testes do modelo OtpCode (ADR-025)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.otp_code import OtpCode
from tests.utils.phone import generate_valid_phone_e164


class TestOtpCode:
    def test_create_otp_code_with_valid_fields(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        otp = otp_code_factory()

        assert otp.id is not None
        assert otp.phone.startswith("+55")
        assert len(otp.code_hash) == 64
        assert otp.expires_at is not None
        assert otp.consumed_at is None
        assert otp.attempts == 0
        assert otp.created_at is not None
        assert otp.updated_at is not None

    def test_phone_without_plus_rejected(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            OtpCode(
                phone="5531999887766",
                code_hash="a" * 64,
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )

    def test_phone_with_letters_rejected(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            OtpCode(
                phone="+5531abc887766",
                code_hash="a" * 64,
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )

    def test_attempts_default_zero(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        otp = otp_code_factory()
        assert otp.attempts == 0

    def test_attempts_cannot_be_negative(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        with pytest.raises(IntegrityError):
            otp_code_factory(attempts=-1)

    def test_consumed_at_nullable(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        otp = otp_code_factory()
        db_session.flush()
        db_session.refresh(otp)
        assert otp.consumed_at is None

    def test_consumed_at_can_be_set(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        otp = otp_code_factory()
        now = datetime.now(UTC)
        otp.consumed_at = now
        db_session.flush()
        db_session.refresh(otp)
        assert otp.consumed_at is not None

    def test_expires_at_required(
        self,
        db_session: Session,
    ) -> None:
        otp = OtpCode(
            phone=generate_valid_phone_e164(),
            code_hash="a" * 64,
        )
        db_session.add(otp)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_code_hash_required(
        self,
        db_session: Session,
    ) -> None:
        otp = OtpCode(
            phone=generate_valid_phone_e164(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db_session.add(otp)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_multiple_otp_codes_same_phone_allowed(
        self,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        """phone não é UNIQUE em OtpCode — múltiplos códigos por telefone permitidos."""
        phone = generate_valid_phone_e164()
        otp1 = otp_code_factory(phone=phone)
        otp2 = otp_code_factory(phone=phone)

        assert otp1.id != otp2.id
        assert otp1.phone == otp2.phone

    def test_repr_contains_core_fields(
        self,
        otp_code_factory: Any,
    ) -> None:
        otp = otp_code_factory()
        text = repr(otp)

        assert str(otp.id) in text
        assert otp.phone in text
        assert "consumed=False" in text
        assert "attempts=0" in text
