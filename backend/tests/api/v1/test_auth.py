"""Testes do endpoint POST /api/v1/auth/request-otp."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.otp_code import OtpCode
from app.services.sms.base import MAGIC_FAILURE_PHONE


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
