"""Testes E2E dos endpoints /api/v1/customers/me/addresses (ADR-027 dec. 8-10).

Endpoints cobertos:
- GET    /api/v1/customers/me/addresses             (200, 401, 404)
- POST   /api/v1/customers/me/addresses             (201, 401, 404, 422)
- PATCH  /api/v1/customers/me/addresses/{id}        (200, 401, 404, 422)
- DELETE /api/v1/customers/me/addresses/{id}        (204, 401, 404)
"""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.address import Address


def _valid_address_payload(city_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "city_id": str(city_id),
        "address_type": "home",
        "is_default": False,
        "street": "Rua das Flores",
        "number": "123",
        "neighborhood": "Centro",
        "zip_code": "35855000",
    }
    payload.update(overrides)
    return payload


# === GET /api/v1/customers/me/addresses ===


class TestListMyAddresses:
    def test_returns_200_empty_list_when_no_addresses(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        """ADR-027 dec. E: lista vazia retorna 200 com []."""
        customer_factory(user=authenticated_user)
        response = authenticated_client.get("/api/v1/customers/me/addresses")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_200_with_addresses(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        customer = customer_factory(user=authenticated_user)
        address_factory(customer=customer)
        address_factory(customer=customer)

        response = authenticated_client.get("/api/v1/customers/me/addresses")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2

    def test_default_address_appears_first(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        """Ordering: is_default DESC, created_at DESC."""
        customer = customer_factory(user=authenticated_user)
        address_factory(customer=customer, is_default=False, street="Não-default")
        default_addr = address_factory(customer=customer, is_default=True, street="Default")

        response = authenticated_client.get("/api/v1/customers/me/addresses")
        body = response.json()
        assert body[0]["id"] == str(default_addr.id)
        assert body[0]["is_default"] is True

    def test_returns_404_when_customer_not_created(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        """ADR-027 C/D: cliente sem Customer → 404 customer_not_found."""
        response = authenticated_client.get("/api/v1/customers/me/addresses")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "customer_not_found"

    def test_returns_401_without_token(self, client: TestClient) -> None:
        response = client.get("/api/v1/customers/me/addresses")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"

    def test_does_not_show_other_customers_addresses(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
        user_factory: Any,
    ) -> None:
        """Isolation: cliente vê apenas seus próprios addresses."""
        my_customer = customer_factory(user=authenticated_user)
        my_addr = address_factory(customer=my_customer)
        # Outro user/customer com 2 addresses
        other_customer = customer_factory()
        address_factory(customer=other_customer)
        address_factory(customer=other_customer)

        response = authenticated_client.get("/api/v1/customers/me/addresses")
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == str(my_addr.id)


# === POST /api/v1/customers/me/addresses ===


class TestCreateMyAddress:
    def test_returns_201_with_full_address(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        city_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user)
        city = city_factory()
        payload = _valid_address_payload(city.id)
        response = authenticated_client.post("/api/v1/customers/me/addresses", json=payload)

        assert response.status_code == 201
        body = response.json()
        assert body["street"] == "Rua das Flores"
        assert body["city_id"] == str(city.id)
        assert body["is_default"] is False

    def test_returns_404_when_customer_not_created(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        city_factory: Any,
    ) -> None:
        city = city_factory()
        response = authenticated_client.post(
            "/api/v1/customers/me/addresses",
            json=_valid_address_payload(city.id),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "customer_not_found"

    def test_returns_422_when_city_id_does_not_exist(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        """ADR-027 D5: city_id inexistente → 422 city_not_found."""
        customer_factory(user=authenticated_user)
        nonexistent_city = uuid.uuid4()
        response = authenticated_client.post(
            "/api/v1/customers/me/addresses",
            json=_valid_address_payload(nonexistent_city),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "city_not_found"

    def test_returns_422_when_required_fields_missing(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user)
        response = authenticated_client.post(
            "/api/v1/customers/me/addresses",
            json={},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"

    def test_returns_422_when_zip_code_invalid_format(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        city_factory: Any,
    ) -> None:
        """zip_code pattern: 8 dígitos numéricos."""
        customer_factory(user=authenticated_user)
        city = city_factory()
        response = authenticated_client.post(
            "/api/v1/customers/me/addresses",
            json=_valid_address_payload(city.id, zip_code="35855-00"),
        )
        assert response.status_code == 422

    def test_returns_422_when_address_type_invalid(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        city_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user)
        city = city_factory()
        response = authenticated_client.post(
            "/api/v1/customers/me/addresses",
            json=_valid_address_payload(city.id, address_type="invalid"),
        )
        assert response.status_code == 422

    def test_returns_401_without_token(self, client: TestClient, city_factory: Any) -> None:
        city = city_factory()
        response = client.post(
            "/api/v1/customers/me/addresses",
            json=_valid_address_payload(city.id),
        )
        assert response.status_code == 401


# === PATCH /api/v1/customers/me/addresses/{id} ===


class TestUpdateMyAddress:
    def test_returns_200_when_updating_street(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        customer = customer_factory(user=authenticated_user)
        address = address_factory(customer=customer, street="Velha")
        response = authenticated_client.patch(
            f"/api/v1/customers/me/addresses/{address.id}",
            json={"street": "Nova"},
        )
        assert response.status_code == 200
        assert response.json()["street"] == "Nova"

    def test_partial_update_keeps_other_fields(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        customer = customer_factory(user=authenticated_user)
        address = address_factory(customer=customer, street="X", number="123")
        response = authenticated_client.patch(
            f"/api/v1/customers/me/addresses/{address.id}",
            json={"street": "Y"},  # number omitido
        )
        body = response.json()
        assert body["street"] == "Y"
        assert body["number"] == "123"

    def test_returns_404_when_address_not_found(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user)
        fake_id = uuid.uuid4()
        response = authenticated_client.patch(
            f"/api/v1/customers/me/addresses/{fake_id}",
            json={"street": "X"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "address_not_found"

    def test_returns_404_when_address_belongs_to_other_customer(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        """ADR-027 A: UUID opacity — não diferencia 'não existe' de 'não é seu'."""
        customer_factory(user=authenticated_user)
        other_customer = customer_factory()
        other_addr = address_factory(customer=other_customer)
        response = authenticated_client.patch(
            f"/api/v1/customers/me/addresses/{other_addr.id}",
            json={"street": "Tentando hackear"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "address_not_found"

    def test_returns_404_when_customer_not_created(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        fake_id = uuid.uuid4()
        response = authenticated_client.patch(
            f"/api/v1/customers/me/addresses/{fake_id}",
            json={"street": "X"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "customer_not_found"

    def test_returns_422_when_city_id_invalid(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        customer = customer_factory(user=authenticated_user)
        address = address_factory(customer=customer)
        nonexistent_city = uuid.uuid4()
        response = authenticated_client.patch(
            f"/api/v1/customers/me/addresses/{address.id}",
            json={"city_id": str(nonexistent_city)},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "city_not_found"

    def test_returns_422_when_address_id_not_uuid(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user)
        response = authenticated_client.patch(
            "/api/v1/customers/me/addresses/not-a-uuid",
            json={"street": "X"},
        )
        assert response.status_code == 422

    def test_returns_401_without_token(
        self,
        client: TestClient,
    ) -> None:
        fake_id = uuid.uuid4()
        response = client.patch(
            f"/api/v1/customers/me/addresses/{fake_id}",
            json={"street": "X"},
        )
        assert response.status_code == 401


# === DELETE /api/v1/customers/me/addresses/{id} ===


class TestDeleteMyAddress:
    def test_returns_204_on_soft_delete(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
        db_session: Session,
    ) -> None:
        customer = customer_factory(user=authenticated_user)
        address = address_factory(customer=customer)
        response = authenticated_client.delete(f"/api/v1/customers/me/addresses/{address.id}")

        assert response.status_code == 204
        # Soft-delete: row ainda existe, deleted_at populado
        from datetime import datetime as _dt

        result = db_session.execute(select(Address).where(Address.id == address.id)).scalar_one()
        assert result.deleted_at is not None
        assert isinstance(result.deleted_at, _dt)

    def test_deleted_address_not_in_list(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        customer = customer_factory(user=authenticated_user)
        keep = address_factory(customer=customer)
        delete = address_factory(customer=customer)

        authenticated_client.delete(f"/api/v1/customers/me/addresses/{delete.id}")
        response = authenticated_client.get("/api/v1/customers/me/addresses")

        ids = {a["id"] for a in response.json()}
        assert str(keep.id) in ids
        assert str(delete.id) not in ids

    def test_returns_404_when_address_not_found(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user)
        fake_id = uuid.uuid4()
        response = authenticated_client.delete(f"/api/v1/customers/me/addresses/{fake_id}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "address_not_found"

    def test_returns_404_when_address_belongs_to_other_customer(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        customer_factory(user=authenticated_user)
        other_customer = customer_factory()
        other_addr = address_factory(customer=other_customer)
        response = authenticated_client.delete(f"/api/v1/customers/me/addresses/{other_addr.id}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "address_not_found"

    def test_returns_404_when_customer_not_created(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
    ) -> None:
        fake_id = uuid.uuid4()
        response = authenticated_client.delete(f"/api/v1/customers/me/addresses/{fake_id}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "customer_not_found"

    def test_returns_401_without_token(self, client: TestClient) -> None:
        fake_id = uuid.uuid4()
        response = client.delete(f"/api/v1/customers/me/addresses/{fake_id}")
        assert response.status_code == 401


# === is_default semântica (ADR-027 dec. 8, 9, 10) — 7 cenários explícitos ===


class TestAddressIsDefault:
    def test_post_is_default_true_when_no_existing_default(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        city_factory: Any,
    ) -> None:
        """Cenário 1: POST is_default=true sem default existente → vira default."""
        customer_factory(user=authenticated_user)
        city = city_factory()
        response = authenticated_client.post(
            "/api/v1/customers/me/addresses",
            json=_valid_address_payload(city.id, is_default=True),
        )
        assert response.status_code == 201
        assert response.json()["is_default"] is True

    def test_post_is_default_true_swaps_existing_default(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
        city_factory: Any,
    ) -> None:
        """Cenário 2: POST is_default=true com outro default → swap atômico."""
        customer = customer_factory(user=authenticated_user)
        old_default = address_factory(customer=customer, is_default=True)
        city = city_factory()

        response = authenticated_client.post(
            "/api/v1/customers/me/addresses",
            json=_valid_address_payload(city.id, is_default=True),
        )
        assert response.status_code == 201
        new_addr_id = response.json()["id"]

        # Lista deve mostrar novo como default e antigo como false
        list_response = authenticated_client.get("/api/v1/customers/me/addresses")
        items_by_id = {a["id"]: a for a in list_response.json()}
        assert items_by_id[new_addr_id]["is_default"] is True
        assert items_by_id[str(old_default.id)]["is_default"] is False

    def test_post_is_default_false_keeps_no_default(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        city_factory: Any,
    ) -> None:
        """Cenário 3: POST is_default=false sem default → permanece sem default (Dec. 9)."""
        customer_factory(user=authenticated_user)
        city = city_factory()
        response = authenticated_client.post(
            "/api/v1/customers/me/addresses",
            json=_valid_address_payload(city.id, is_default=False),
        )
        assert response.status_code == 201
        list_response = authenticated_client.get("/api/v1/customers/me/addresses")
        defaults = [a for a in list_response.json() if a["is_default"]]
        assert defaults == []

    def test_patch_is_default_true_swaps_with_existing(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        """Cenário 4: PATCH is_default=true em endereço false, com outro default → swap."""
        customer = customer_factory(user=authenticated_user)
        old_default = address_factory(customer=customer, is_default=True)
        candidate = address_factory(customer=customer, is_default=False)

        response = authenticated_client.patch(
            f"/api/v1/customers/me/addresses/{candidate.id}",
            json={"is_default": True},
        )
        assert response.status_code == 200
        assert response.json()["is_default"] is True

        # Antigo default agora false
        list_response = authenticated_client.get("/api/v1/customers/me/addresses")
        items_by_id = {a["id"]: a for a in list_response.json()}
        assert items_by_id[str(candidate.id)]["is_default"] is True
        assert items_by_id[str(old_default.id)]["is_default"] is False

    def test_patch_is_default_false_clears_default(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        """Cenário 5: PATCH is_default=false em default → fica sem default (Dec. 9)."""
        customer = customer_factory(user=authenticated_user)
        was_default = address_factory(customer=customer, is_default=True)

        response = authenticated_client.patch(
            f"/api/v1/customers/me/addresses/{was_default.id}",
            json={"is_default": False},
        )
        assert response.status_code == 200
        assert response.json()["is_default"] is False

        list_response = authenticated_client.get("/api/v1/customers/me/addresses")
        defaults = [a for a in list_response.json() if a["is_default"]]
        assert defaults == []

    def test_delete_default_does_not_auto_promote(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        """Cenário 6: DELETE de default → soft-delete + cliente fica sem default (Dec. 10)."""
        customer = customer_factory(user=authenticated_user)
        default_addr = address_factory(customer=customer, is_default=True)
        non_default = address_factory(customer=customer, is_default=False)

        response = authenticated_client.delete(f"/api/v1/customers/me/addresses/{default_addr.id}")
        assert response.status_code == 204

        list_response = authenticated_client.get("/api/v1/customers/me/addresses")
        items = list_response.json()
        assert len(items) == 1
        # Não-default NÃO virou default automaticamente (Dec. 10)
        assert items[0]["id"] == str(non_default.id)
        assert items[0]["is_default"] is False

    def test_delete_non_default_does_not_affect_default(
        self,
        authenticated_client: TestClient,
        authenticated_user: Any,
        customer_factory: Any,
        address_factory: Any,
    ) -> None:
        """Cenário 7: DELETE de não-default → default permanece intacto."""
        customer = customer_factory(user=authenticated_user)
        default_addr = address_factory(customer=customer, is_default=True)
        non_default = address_factory(customer=customer, is_default=False)

        response = authenticated_client.delete(f"/api/v1/customers/me/addresses/{non_default.id}")
        assert response.status_code == 204

        list_response = authenticated_client.get("/api/v1/customers/me/addresses")
        items = list_response.json()
        assert len(items) == 1
        assert items[0]["id"] == str(default_addr.id)
        assert items[0]["is_default"] is True
