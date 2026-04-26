"""Testes E2E dos endpoints /api/v1/customers/me e /api/v1/customers (ADR-027).

Endpoints cobertos:
- GET /api/v1/customers/me (200, 404, 401)
- POST /api/v1/customers (201, 409, 422, 401)
- PATCH /api/v1/customers/me (200, 404, 422, 401)
"""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

VALID_CPF = "52998224725"
VALID_CPF_2 = "11144477735"


# === GET /api/v1/customers/me ===


class TestGetMyCustomer:
    def test_returns_200_when_customer_exists(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        customer = customer_factory(user=authenticated_user, name="João Silva")
        response = authenticated_client.get("/api/v1/customers/me")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(customer.id)
        assert body["name"] == "João Silva"
        assert body["phone"] == authenticated_user.phone

    def test_returns_404_when_customer_not_created_yet(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        """Lazy creation (ADR-027 dec. 2): User existe mas Customer não."""
        response = authenticated_client.get("/api/v1/customers/me")

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "customer_not_found"

    def test_returns_401_when_no_authorization_header(
        self,
        client: TestClient,
    ) -> None:
        response = client.get("/api/v1/customers/me")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"

    def test_response_includes_all_expected_fields(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user, name="João", cpf=VALID_CPF)
        response = authenticated_client.get("/api/v1/customers/me")
        body = response.json()
        expected = {"id", "phone", "name", "email", "cpf", "birth_date", "created_at", "updated_at"}
        assert set(body.keys()) == expected

    def test_response_does_not_expose_internal_fields(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        """user_id, is_active, deleted_at não devem aparecer (ADR-027)."""
        customer_factory(user=authenticated_user)
        response = authenticated_client.get("/api/v1/customers/me")
        keys = set(response.json().keys())
        forbidden = {"user_id", "is_active", "deleted_at"}
        assert not (keys & forbidden), f"Internal fields leaked: {keys & forbidden}"


# === POST /api/v1/customers ===


class TestCreateMyCustomer:
    def test_returns_201_with_minimum_payload(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        """ADR-027 dec. 3: POST mínimo só com name."""
        response = authenticated_client.post(
            "/api/v1/customers",
            json={"name": "João Silva"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "João Silva"
        assert body["phone"] == authenticated_user.phone  # ADR-027 dec. 6
        assert body["email"] is None
        assert body["cpf"] is None
        assert body["birth_date"] is None

    def test_returns_201_with_full_payload(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        response = authenticated_client.post(
            "/api/v1/customers",
            json={
                "name": "João Silva",
                "email": "joao@example.com",
                "cpf": VALID_CPF,
                "birth_date": "1990-05-15",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "joao@example.com"
        assert body["cpf"] == VALID_CPF
        assert body["birth_date"] == "1990-05-15"

    def test_phone_comes_from_user_not_from_body(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        """ADR-027 dec. 6: phone do User logado, ignora qualquer phone no body.

        extra='forbid' no schema rejeita phone se enviado.
        """
        response = authenticated_client.post(
            "/api/v1/customers",
            json={"name": "João", "phone": "+5511999999999"},
        )
        # extra='forbid' rejeita phone no body
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_returns_409_when_customer_already_exists(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        """ADR-027 dec. 4: 409 Conflict se User já tem Customer."""
        customer_factory(user=authenticated_user)
        response = authenticated_client.post(
            "/api/v1/customers",
            json={"name": "Outro Nome"},
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "customer_already_exists"

    def test_returns_422_when_name_missing(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        response = authenticated_client.post(
            "/api/v1/customers",
            json={},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_returns_422_when_name_empty_string(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        """min_length=1 rejeita string vazia."""
        response = authenticated_client.post(
            "/api/v1/customers",
            json={"name": ""},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_returns_401_when_no_authorization_header(
        self,
        client: TestClient,
    ) -> None:
        response = client.post(
            "/api/v1/customers",
            json={"name": "João"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"


# === PATCH /api/v1/customers/me ===


class TestUpdateMyCustomer:
    def test_returns_200_when_updating_name(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user, name="Nome Antigo")
        response = authenticated_client.patch(
            "/api/v1/customers/me",
            json={"name": "Nome Novo"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Nome Novo"

    def test_partial_update_only_changes_sent_fields(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        """ADR-027 dec. 8: omitir campo mantém valor atual."""
        customer_factory(
            user=authenticated_user,
            name="Original",
            email="original@example.com",
            cpf=VALID_CPF,
        )
        response = authenticated_client.patch(
            "/api/v1/customers/me",
            json={"name": "Novo Nome"},  # email e cpf omitidos
        )

        body = response.json()
        assert body["name"] == "Novo Nome"
        assert body["email"] == "original@example.com"  # mantido
        assert body["cpf"] == VALID_CPF  # mantido

    def test_explicit_null_clears_field(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        """ADR-027 dec. 8: enviar null limpa o campo."""
        customer_factory(
            user=authenticated_user,
            email="original@example.com",
            cpf=VALID_CPF,
        )
        response = authenticated_client.patch(
            "/api/v1/customers/me",
            json={"email": None},
        )

        body = response.json()
        assert body["email"] is None
        assert body["cpf"] == VALID_CPF  # cpf não mexido

    def test_returns_404_when_customer_not_created(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        response = authenticated_client.patch(
            "/api/v1/customers/me",
            json={"name": "Tentando atualizar sem ter criado"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "customer_not_found"

    def test_returns_422_when_name_empty_string(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user)
        response = authenticated_client.patch(
            "/api/v1/customers/me",
            json={"name": ""},
        )

        assert response.status_code == 422

    def test_returns_422_when_phone_in_body_extra_forbid(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        """ADR-027 dec. 7: phone imutável — extra='forbid' rejeita."""
        customer_factory(user=authenticated_user)
        response = authenticated_client.patch(
            "/api/v1/customers/me",
            json={"phone": "+5511999999999"},
        )

        assert response.status_code == 422

    def test_returns_401_when_no_authorization_header(
        self,
        client: TestClient,
    ) -> None:
        response = client.patch(
            "/api/v1/customers/me",
            json={"name": "Tentando sem token"},
        )

        assert response.status_code == 401


# === Conflict edge case: 2 Users diferentes podem cadastrar Customer cada um ===


class TestCustomerIsolation:
    def test_two_users_can_each_have_own_customer(
        self,
        client: TestClient,
        db_session: Session,
        user_factory: Any,
        customer_factory: Any,
    ) -> None:
        """UNIQUE em user_id permite 1 Customer por User (não global)."""
        from app.services.auth.jwt import create_access_token

        user_a = user_factory()
        user_b = user_factory()

        customer_a = customer_factory(user=user_a, name="Cliente A")
        customer_b = customer_factory(user=user_b, name="Cliente B")

        # User A consulta SEU Customer
        token_a = create_access_token(user_id=user_a.id, phone=user_a.phone)
        client.headers["Authorization"] = f"Bearer {token_a}"
        resp_a = client.get("/api/v1/customers/me")
        assert resp_a.status_code == 200
        assert resp_a.json()["id"] == str(customer_a.id)

        # User B consulta SEU Customer (diferente)
        token_b = create_access_token(user_id=user_b.id, phone=user_b.phone)
        client.headers["Authorization"] = f"Bearer {token_b}"
        resp_b = client.get("/api/v1/customers/me")
        assert resp_b.status_code == 200
        assert resp_b.json()["id"] == str(customer_b.id)
        assert resp_b.json()["id"] != str(customer_a.id)
