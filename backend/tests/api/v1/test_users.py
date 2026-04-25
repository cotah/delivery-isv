"""Testes do endpoint GET /api/v1/users/me e dos cenários de 401."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from app.core.config import get_settings
from app.models.user import User
from app.services.auth.jwt import JWT_ALGORITHM, create_access_token


def _encode_with_claims(claims: dict[str, object]) -> str:
    """Helper: monta JWT com claims arbitrários (assina com secret do app)."""
    settings = get_settings()
    return jose_jwt.encode(
        claims,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


class TestGetCurrentUserEndpoint:
    def test_returns_200_with_user_data_when_authenticated(
        self,
        authenticated_client: TestClient,
        authenticated_user: User,
    ) -> None:
        response = authenticated_client.get("/api/v1/users/me")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(authenticated_user.id)
        assert body["phone"] == authenticated_user.phone

    def test_response_includes_phone(
        self,
        authenticated_client: TestClient,
        authenticated_user: User,
    ) -> None:
        response = authenticated_client.get("/api/v1/users/me")
        assert response.json()["phone"] == authenticated_user.phone

    def test_response_includes_id_as_uuid_string(
        self,
        authenticated_client: TestClient,
    ) -> None:
        response = authenticated_client.get("/api/v1/users/me")
        body = response.json()

        # Deve ser parseável como UUID
        uuid.UUID(body["id"])

    def test_response_includes_timestamps(
        self,
        authenticated_client: TestClient,
    ) -> None:
        response = authenticated_client.get("/api/v1/users/me")
        body = response.json()

        assert "created_at" in body
        assert "updated_at" in body
        # Devem ser parseáveis como datetime ISO
        datetime.fromisoformat(body["created_at"])
        datetime.fromisoformat(body["updated_at"])


class TestGetCurrentUser401:
    def test_returns_401_unauthenticated_when_no_authorization_header(
        self,
        client: TestClient,
    ) -> None:
        response = client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"

    def test_returns_401_unauthenticated_when_no_bearer_prefix(
        self,
        client: TestClient,
    ) -> None:
        # Header sem "Bearer " — HTTPBearer rejeita pré-resolução
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "abc123notbearer"},
        )

        assert response.status_code == 401
        # Sem prefix Bearer, FastAPI/HTTPBearer não popula credentials → unauthenticated
        assert response.json()["error"]["code"] == "unauthenticated"

    def test_returns_401_token_expired_when_jwt_exp_in_past(
        self,
        client: TestClient,
        authenticated_user: User,
    ) -> None:
        past_exp = datetime.now(UTC) - timedelta(minutes=1)
        past_iat = datetime.now(UTC) - timedelta(hours=1)
        expired_token = _encode_with_claims(
            {
                "sub": str(authenticated_user.id),
                "phone": authenticated_user.phone,
                "iat": int(past_iat.timestamp()),
                "exp": int(past_exp.timestamp()),
                "type": "access",
            }
        )

        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "token_expired"

    def test_returns_401_invalid_token_when_jwt_signature_wrong(
        self,
        client: TestClient,
        authenticated_user: User,
    ) -> None:
        now = datetime.now(UTC)
        claims = {
            "sub": str(authenticated_user.id),
            "phone": authenticated_user.phone,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=60)).timestamp()),
            "type": "access",
        }
        # Assinado com secret diferente
        bad_token = jose_jwt.encode(claims, "some-other-secret-xyz", algorithm=JWT_ALGORITHM)

        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"

    def test_returns_401_invalid_token_when_jwt_malformed(
        self,
        client: TestClient,
    ) -> None:
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer not-a-jwt-at-all"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"

    def test_returns_401_invalid_token_when_user_id_does_not_exist(
        self,
        client: TestClient,
    ) -> None:
        # JWT válido com user_id que não existe no banco
        nonexistent_id = uuid.uuid4()
        token = create_access_token(user_id=nonexistent_id, phone="+5531999887766")

        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"


class TestErrorBodyShape:
    def test_401_unauthenticated_body_has_code_and_message(
        self,
        client: TestClient,
    ) -> None:
        response = client.get("/api/v1/users/me")
        body = response.json()

        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "Autenticação" in body["error"]["message"]

    def test_401_token_expired_body_has_code_and_message(
        self,
        client: TestClient,
        authenticated_user: User,
    ) -> None:
        past_exp = datetime.now(UTC) - timedelta(minutes=1)
        past_iat = datetime.now(UTC) - timedelta(hours=1)
        expired_token = _encode_with_claims(
            {
                "sub": str(authenticated_user.id),
                "phone": authenticated_user.phone,
                "iat": int(past_iat.timestamp()),
                "exp": int(past_exp.timestamp()),
                "type": "access",
            }
        )

        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        body = response.json()

        assert body["error"]["code"] == "token_expired"
        assert "expirada" in body["error"]["message"].lower()

    def test_401_invalid_token_body_has_code_and_message(
        self,
        client: TestClient,
    ) -> None:
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer garbage"},
        )
        body = response.json()

        assert body["error"]["code"] == "invalid_token"
        assert "inválido" in body["error"]["message"].lower()

    def test_401_responses_have_www_authenticate_header(
        self,
        client: TestClient,
    ) -> None:
        """RFC 6750: respostas 401 devem ter WWW-Authenticate."""
        response = client.get("/api/v1/users/me")

        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert "www-authenticate" in headers_lower
        assert "bearer" in headers_lower["www-authenticate"].lower()

    def test_token_expired_message_differs_from_invalid_token_message(
        self,
        client: TestClient,
        authenticated_user: User,
    ) -> None:
        """Diferenciação UX: token_expired e invalid_token têm mensagens distintas."""
        past_exp = datetime.now(UTC) - timedelta(minutes=1)
        expired_token = _encode_with_claims(
            {
                "sub": str(authenticated_user.id),
                "phone": authenticated_user.phone,
                "iat": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
                "exp": int(past_exp.timestamp()),
                "type": "access",
            }
        )

        r_expired = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        r_invalid = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer garbage"},
        )

        assert r_expired.json()["error"]["message"] != r_invalid.json()["error"]["message"]


class TestSecurityLogging:
    def test_malformed_token_logs_warning(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="app.api.deps"):
            client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer garbage"},
            )

        assert "auth.malformed_token" in caplog.text

    def test_user_not_found_logs_warning(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        nonexistent_id = uuid.uuid4()
        token = create_access_token(user_id=nonexistent_id, phone="+5531999887766")

        with caplog.at_level(logging.WARNING, logger="app.api.deps"):
            client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert "auth.user_not_found" in caplog.text

    def test_token_expired_does_not_log_warning(
        self,
        client: TestClient,
        authenticated_user: User,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Fluxo normal — não loga (acontece a cada 60min em uso real)."""
        past_exp = datetime.now(UTC) - timedelta(minutes=1)
        expired_token = _encode_with_claims(
            {
                "sub": str(authenticated_user.id),
                "phone": authenticated_user.phone,
                "iat": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
                "exp": int(past_exp.timestamp()),
                "type": "access",
            }
        )

        with caplog.at_level(logging.WARNING, logger="app.api.deps"):
            client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            )

        assert "auth.malformed_token" not in caplog.text
        assert "auth.user_not_found" not in caplog.text

    def test_unauthenticated_does_not_log_warning(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Header ausente é normal — não loga."""
        with caplog.at_level(logging.WARNING, logger="app.api.deps"):
            client.get("/api/v1/users/me")

        assert "auth.malformed_token" not in caplog.text
        assert "auth.user_not_found" not in caplog.text
