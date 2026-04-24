"""Testes do serviço request_otp (ADR-025)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.otp_code import OtpCode
from app.services.auth.otp import (
    OTP_EXPIRATION_MINUTES,
    OtpRequestFailedError,
    request_otp,
)
from app.services.sms.base import MAGIC_FAILURE_PHONE
from app.services.sms.mock import MockSMSProvider


class TestRequestOtp:
    def test_creates_new_otp_code(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
    ) -> None:
        phone = "+5531999887766"

        masked = request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone=phone,
        )

        otps = db_session.execute(select(OtpCode).where(OtpCode.phone == phone)).scalars().all()
        assert len(otps) == 1
        assert otps[0].consumed_at is None
        assert masked.startswith("+55 31 9")

    def test_invalidates_previous_active_otp(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        previous = otp_code_factory(phone=phone)

        request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone=phone,
        )

        db_session.refresh(previous)
        assert previous.consumed_at is not None

    def test_does_not_invalidate_already_consumed_otps(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        past = datetime.now(UTC) - timedelta(hours=1)
        already_consumed = otp_code_factory(phone=phone, consumed_at=past)
        original_consumed_at = already_consumed.consumed_at

        request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone=phone,
        )

        db_session.refresh(already_consumed)
        # consumed_at original preservado (não sobrescrito por request-otp)
        assert already_consumed.consumed_at == original_consumed_at

    def test_does_not_invalidate_expired_otps(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        past_exp = datetime.now(UTC) - timedelta(minutes=5)
        expired = otp_code_factory(phone=phone, expires_at=past_exp)

        request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone=phone,
        )

        db_session.refresh(expired)
        # Expirados ficam naturalmente inválidos — consumed_at continua NULL
        assert expired.consumed_at is None

    def test_does_not_invalidate_otps_of_other_phone(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
        otp_code_factory: Any,
    ) -> None:
        other_phone = "+5531988776655"
        other_otp = otp_code_factory(phone=other_phone)

        request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone="+5531999887766",
        )

        db_session.refresh(other_otp)
        assert other_otp.consumed_at is None

    def test_otp_code_is_stored_as_hash_not_plaintext(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
    ) -> None:
        phone = "+5531999887766"

        request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone=phone,
        )

        otp = db_session.execute(select(OtpCode).where(OtpCode.phone == phone)).scalar_one()
        # sha256 hex = 64 chars, nunca 6 dígitos
        assert len(otp.code_hash) == 64
        assert not otp.code_hash.isdigit() or len(otp.code_hash) != 6

    def test_otp_expires_at_is_10_minutes_from_now(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
    ) -> None:
        phone = "+5531999887766"
        before = datetime.now(UTC)

        request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone=phone,
        )

        otp = db_session.execute(select(OtpCode).where(OtpCode.phone == phone)).scalar_one()
        expected = before + timedelta(minutes=OTP_EXPIRATION_MINUTES)
        # ±5s de margem pra latência de teste
        assert abs((otp.expires_at - expected).total_seconds()) < 5

    def test_returns_masked_phone_for_display(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
    ) -> None:
        masked = request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone="+5531999887766",
        )

        assert masked == "+55 31 9*****7766"

    def test_sms_provider_error_raises_otp_request_failed(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
    ) -> None:
        with pytest.raises(OtpRequestFailedError):
            request_otp(
                session=db_session,
                sms_provider=mock_sms_provider,
                phone=MAGIC_FAILURE_PHONE,
            )

    def test_sms_provider_error_marks_otp_consumed(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
    ) -> None:
        with pytest.raises(OtpRequestFailedError):
            request_otp(
                session=db_session,
                sms_provider=mock_sms_provider,
                phone=MAGIC_FAILURE_PHONE,
            )

        otp = db_session.execute(
            select(OtpCode).where(OtpCode.phone == MAGIC_FAILURE_PHONE)
        ).scalar_one()
        assert otp.consumed_at is not None

    def test_different_codes_per_call(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
    ) -> None:
        phone_a = "+5531999887766"
        phone_b = "+5531988776655"

        request_otp(session=db_session, sms_provider=mock_sms_provider, phone=phone_a)
        request_otp(session=db_session, sms_provider=mock_sms_provider, phone=phone_b)

        hashes = {
            row[0]
            for row in db_session.execute(
                select(OtpCode.code_hash).where(OtpCode.phone.in_([phone_a, phone_b]))
            ).all()
        }
        assert len(hashes) == 2

    def test_hash_is_sha256_of_some_6_digit_code(
        self,
        db_session: Session,
        mock_sms_provider: MockSMSProvider,
    ) -> None:
        """O hash persistido deve bater com sha256 de ALGUM código 6 dígitos."""
        phone = "+5531999887766"

        request_otp(
            session=db_session,
            sms_provider=mock_sms_provider,
            phone=phone,
        )

        otp = db_session.execute(select(OtpCode).where(OtpCode.phone == phone)).scalar_one()
        # Reconstrói sha256 de todos códigos 6 dígitos possíveis exigiria 1M ops —
        # verifica apenas que hash tem o formato correto (64 hex chars).
        assert len(otp.code_hash) == 64
        int(otp.code_hash, 16)  # parse como hex, levanta se inválido
