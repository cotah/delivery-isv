"""Lógica de negócio de Address (ADR-020 layer: service, ADR-027 dec. 8-10).

Reusa CustomerNotFoundError do customer.py (cliente sem Customer cadastrado
não pode operar em endereços — pre-condição checada antes de qualquer
operação de Address).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.address import Address
from app.models.city import City
from app.models.user import User
from app.repositories import address as address_repository
from app.repositories import customer as customer_repository
from app.schemas.address import AddressCreate, AddressUpdate
from app.services.customer import CustomerNotFoundError

# === Hierarquia de exceções (pattern CP2 customer.py) ===


class AddressError(Exception):
    """Base de exceções do domínio Address."""


class AddressNotFoundError(AddressError):
    """Address não existe OU pertence a outro customer (404 disfarçado, ADR-027)."""


class CityNotFoundError(AddressError):
    """city_id não existe — vira 422 validation_failed no endpoint (ADR-027 D5)."""


# === Helpers ===


def _ensure_city_exists(session: Session, city_id: UUID) -> None:
    """Valida city_id pre-insert/update. Raise CityNotFoundError se não existir."""
    city = session.get(City, city_id)
    if city is None:
        raise CityNotFoundError(f"city_id inválido: cidade não cadastrada (id={city_id}).")


def _get_customer_or_raise(session: Session, user: User) -> UUID:
    """Helper interno: garante que User logado tem Customer cadastrado.

    Raise CustomerNotFoundError se ainda não fez POST /customers (ADR-027 dec. 2).
    Retorna customer_id pra uso nas queries de Address.
    """
    customer = customer_repository.get_by_user_id(session, user.id)
    if customer is None:
        raise CustomerNotFoundError(
            "Customer não cadastrado. Use POST /api/v1/customers para criar antes."
        )
    return customer.id


# === Operações CRUD ===


def list_my_addresses(session: Session, user: User) -> list[Address]:
    """GET /customers/me/addresses — lista vazia ou populada (ADR-027 dec. — E confirmada)."""
    customer_id = _get_customer_or_raise(session, user)
    return address_repository.list_active_by_customer(session, customer_id)


def create_my_address(session: Session, user: User, payload: AddressCreate) -> Address:
    """POST /customers/me/addresses (ADR-027 dec. 8-9).

    Lógica is_default (dec. 8 transacional):
    1. _get_customer + _ensure_city_exists (pré-validação)
    2. Se payload.is_default=true: clear_default_for_customer
    3. INSERT do novo Address (já vai com is_default correto)
    4. flush (1 transação implícita do request — UNIQUE parcial protege race)

    Raises:
        CustomerNotFoundError, CityNotFoundError.
    """
    customer_id = _get_customer_or_raise(session, user)
    _ensure_city_exists(session, payload.city_id)

    if payload.is_default:
        # Limpa default existente ANTES de inserir o novo (UNIQUE parcial).
        address_repository.clear_default_for_customer(session, customer_id)

    address = Address(
        customer_id=customer_id,
        city_id=payload.city_id,
        address_type=payload.address_type,
        is_default=payload.is_default,
        street=payload.street,
        number=payload.number,
        complement=payload.complement,
        neighborhood=payload.neighborhood,
        zip_code=payload.zip_code,
        reference_point=payload.reference_point,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return address_repository.create(session, address)


def update_my_address(
    session: Session,
    user: User,
    address_id: UUID,
    payload: AddressUpdate,
) -> Address:
    """PATCH /customers/me/addresses/{id} (ADR-027 dec. 5, 8).

    Pattern exclude_unset=True (ADR-027 dec. 8 do CP2):
    - Campo omitido: mantém valor atual
    - Campo enviado como null: limpa (onde nullable)
    - is_default=true: troca atomicamente (clear outros, set true)
    - is_default=false: Address fica sem flag (cliente pode acabar sem default)

    Raises:
        CustomerNotFoundError, AddressNotFoundError, CityNotFoundError.
    """
    customer_id = _get_customer_or_raise(session, user)

    address = address_repository.get_for_customer(session, address_id, customer_id)
    if address is None:
        raise AddressNotFoundError("Endereço não encontrado ou não pertence ao cliente logado.")

    updates = payload.model_dump(exclude_unset=True)

    # Validação de city_id ANTES de mutar (se enviado).
    if "city_id" in updates and updates["city_id"] is not None:
        _ensure_city_exists(session, updates["city_id"])

    # Troca atômica de default (ADR-027 dec. 8).
    if updates.get("is_default") is True:
        address_repository.clear_default_for_customer(
            session,
            customer_id,
            exclude_address_id=address.id,
        )

    for field, value in updates.items():
        setattr(address, field, value)

    return address_repository.update_address(session, address)


def delete_my_address(session: Session, user: User, address_id: UUID) -> None:
    """DELETE /customers/me/addresses/{id} (ADR-027 dec. 10).

    Soft-delete (Address tem SoftDeleteMixin, RESTRICT em Order preserva histórico).
    NÃO auto-promove outro Address a default (ADR-027 dec. 10 — cliente
    escolhe novo default no próximo pedido).

    Raises:
        CustomerNotFoundError, AddressNotFoundError.
    """
    customer_id = _get_customer_or_raise(session, user)

    address = address_repository.get_for_customer(session, address_id, customer_id)
    if address is None:
        raise AddressNotFoundError("Endereço não encontrado ou não pertence ao cliente logado.")

    address_repository.soft_delete(session, address)
