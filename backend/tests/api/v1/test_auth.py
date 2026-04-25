"""Testes dos endpoints POST /api/v1/auth/request-otp e /verify-otp."""

import hashlib
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.otp_code import OtpCode
from app.models.user import User
from app.services.auth.jwt import decode_access_token
from app.services.sms.base import MAGIC_FAILURE_PHONE


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class TestRequestOtpEndpoint:
    def test_returns_200_with_expected_body(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+5531999887766"},
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"message", "expires_in_seconds"}

    def test_creates_otp_in_db(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        phone = "+5531999887766"

        response = client.post("/api/v1/auth/request-otp", json={"phone": phone})

        assert response.status_code == 200
        otps = db_session.execute(select(OtpCode).where(OtpCode.phone == phone)).scalars().all()
        assert len(otps) == 1
        assert otps[0].consumed_at is None

    def test_masked_phone_in_message(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+5531999887766"},
        )

        message = response.json()["message"]
        assert "+55 31 9*****7766" in message
        # Phone cru nunca deve vazar
        assert "+5531999887766" not in message

    def test_expires_in_seconds_is_600(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+5531999887766"},
        )

        assert response.json()["expires_in_seconds"] == 600

    def test_returns_422_for_phone_without_plus(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "5531999887766"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_returns_422_for_empty_phone(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": ""},
        )

        assert response.status_code == 422

    def test_returns_422_for_phone_with_letters(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+5531abc887766"},
        )

        assert response.status_code == 422

    def test_returns_422_for_missing_phone(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/request-otp", json={})

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_returns_502_when_sms_provider_fails(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": MAGIC_FAILURE_PHONE},
        )

        assert response.status_code == 502
        body = response.json()
        assert body["error"]["code"] == "sms_provider_error"
        assert "SMS" in body["error"]["message"] or "sms" in body["error"]["message"].lower()

    def test_502_otp_is_consumed_in_db(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        response = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": MAGIC_FAILURE_PHONE},
        )

        assert response.status_code == 502
        otp = db_session.execute(
            select(OtpCode).where(OtpCode.phone == MAGIC_FAILURE_PHONE)
        ).scalar_one()
        assert otp.consumed_at is not None

    def test_new_request_invalidates_previous(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        phone = "+5531999887766"

        r1 = client.post("/api/v1/auth/request-otp", json={"phone": phone})
        assert r1.status_code == 200

        r2 = client.post("/api/v1/auth/request-otp", json={"phone": phone})
        assert r2.status_code == 200

        otps = (
            db_session.execute(
                select(OtpCode).where(OtpCode.phone == phone).order_by(OtpCode.created_at)
            )
            .scalars()
            .all()
        )
        assert len(otps) == 2
        # Primeiro OtpCode consumido (invalidado pelo segundo request)
        assert otps[0].consumed_at is not None
        # Segundo OtpCode ativo
        assert otps[1].consumed_at is None


class TestVerifyOtpEndpoint:
    def test_returns_200_with_valid_token_body(
        self,
        client: TestClient,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        otp_code_factory(phone=phone, code_hash=_hash(code))

        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": code},
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"access_token", "token_type", "expires_in_seconds"}
        assert body["token_type"] == "bearer"
        assert body["expires_in_seconds"] == 3600

    def test_returns_jwt_decodable_with_correct_secret(
        self,
        client: TestClient,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        otp_code_factory(phone=phone, code_hash=_hash(code))

        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": code},
        )

        token = response.json()["access_token"]
        payload = decode_access_token(token)
        assert payload.phone == phone
        assert payload.token_type == "access"

    def test_creates_user_in_db_on_success(
        self,
        client: TestClient,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        otp_code_factory(phone=phone, code_hash=_hash(code))

        client.post("/api/v1/auth/verify-otp", json={"phone": phone, "code": code})

        user = db_session.execute(select(User).where(User.phone == phone)).scalar_one()
        assert user is not None

    def test_reuses_user_on_second_login(
        self,
        client: TestClient,
        db_session: Session,
        user_factory: Any,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        code = "123456"
        existing = user_factory(phone=phone)
        otp_code_factory(phone=phone, code_hash=_hash(code))

        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": code},
        )

        assert response.status_code == 200
        token_payload = decode_access_token(response.json()["access_token"])
        assert token_payload.user_id == existing.id


class TestVerifyOtpErrorResponses:
    def test_returns_400_for_wrong_code(
        self,
        client: TestClient,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        otp_code_factory(phone=phone, code_hash=_hash("123456"))

        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": "000000"},
        )

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "invalid_otp_code"

    def test_returns_400_for_nonexistent_phone(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+5531999887766", "code": "123456"},
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_otp_code"

    def test_returns_400_for_expired_otp(
        self,
        client: TestClient,
        otp_code_factory: Any,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        phone = "+5531999887766"
        otp_code_factory(
            phone=phone,
            code_hash=_hash("123456"),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )

        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": "123456"},
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_otp_code"

    def test_returns_400_for_consumed_otp(
        self,
        client: TestClient,
        db_session: Session,
        otp_code_factory: Any,
    ) -> None:
        from datetime import UTC, datetime

        phone = "+5531999887766"
        otp_code_factory(
            phone=phone,
            code_hash=_hash("123456"),
            consumed_at=datetime.now(UTC),
        )

        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": "123456"},
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_otp_code"

    def test_returns_400_for_attempts_exhausted(
        self,
        client: TestClient,
        otp_code_factory: Any,
    ) -> None:
        phone = "+5531999887766"
        otp_code_factory(phone=phone, code_hash=_hash("123456"))

        # 3 tentativas erradas
        for _ in range(3):
            client.post(
                "/api/v1/auth/verify-otp",
                json={"phone": phone, "code": "000000"},
            )

        # 4ª (mesmo código certo): bloqueado
        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": "123456"},
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_otp_code"

    def test_all_400_have_same_message(
        self,
        client: TestClient,
        otp_code_factory: Any,
    ) -> None:
        """Anti-enumeração externa: 5 cenários têm mesma response message."""
        from datetime import UTC, datetime, timedelta

        # Cenário 1: not found
        r1 = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+5531999887766", "code": "123456"},
        )

        # Cenário 2: wrong hash
        otp_code_factory(phone="+5531988776655", code_hash=_hash("123456"))
        r2 = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+5531988776655", "code": "000000"},
        )

        # Cenário 3: expired
        otp_code_factory(
            phone="+5511999887766",
            code_hash=_hash("123456"),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        r3 = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+5511999887766", "code": "123456"},
        )

        msg1 = r1.json()["error"]["message"]
        msg2 = r2.json()["error"]["message"]
        msg3 = r3.json()["error"]["message"]
        assert msg1 == msg2 == msg3

    def test_returns_422_for_invalid_phone_format(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "5531999887766", "code": "123456"},
        )
        assert response.status_code == 422

    def test_returns_422_for_invalid_code_format_letters(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+5531999887766", "code": "abc123"},
        )
        assert response.status_code == 422

    def test_returns_422_for_invalid_code_length(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+5531999887766", "code": "12345"},
        )
        assert response.status_code == 422

    def test_returns_422_for_missing_fields(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/verify-otp", json={})
        assert response.status_code == 422


class TestRateLimit:
    def test_request_otp_rate_limited_by_ip_after_10(self, client: TestClient) -> None:
        """11º request do mesmo IP em <1h deve retornar 429."""
        # 10 primeiros requests ok
        for i in range(10):
            r = client.post(
                "/api/v1/auth/request-otp",
                json={"phone": f"+55319988{i:05d}"},
            )
            # Pode dar 200 ou 502 (magic), mas não 429 ainda
            assert r.status_code != 429

        # 11º deve ser 429
        r11 = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+5531999887766"},
        )
        assert r11.status_code == 429

    def test_verify_otp_rate_limited_by_ip_after_30(
        self,
        client: TestClient,
        otp_code_factory: Any,
    ) -> None:
        """31º request do mesmo IP em <1h deve retornar 429."""
        for i in range(30):
            client.post(
                "/api/v1/auth/verify-otp",
                json={"phone": f"+55319988{i:05d}", "code": "000000"},
            )

        r31 = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+5531999887766", "code": "000000"},
        )
        assert r31.status_code == 429

    def test_429_body_has_retry_after_and_code(self, client: TestClient) -> None:
        # Esgota o limit
        for i in range(11):
            client.post(
                "/api/v1/auth/request-otp",
                json={"phone": f"+55319988{i:05d}"},
            )

        # Próximo
        r = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+5531999887766"},
        )
        assert r.status_code == 429
        body = r.json()
        assert body["error"]["code"] == "rate_limited"
        assert "retry_after_seconds" in body["error"]

    def test_429_header_retry_after_present(self, client: TestClient) -> None:
        for i in range(11):
            client.post(
                "/api/v1/auth/request-otp",
                json={"phone": f"+55319988{i:05d}"},
            )

        r = client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+5531999887766"},
        )
        assert r.status_code == 429
        assert "retry-after" in {k.lower() for k in r.headers}
