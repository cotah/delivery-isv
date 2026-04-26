"""Lógica de negócio de Customer (ADR-020 layer: service, ADR-027).

NÃO confundir com `customer_anonymization.py` (stub LGPD futuro). Este
módulo cobre o ciclo CRUD de Customer (CP2 + CP3 do Ciclo Customer).
"""

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.user import User
from app.repositories import customer as customer_repository
from app.schemas.customer import CustomerCreate, CustomerUpdate

# === Hierarquia de exceções (pattern InvalidOtpError do Auth) ===


class CustomerError(Exception):
    """Base de exceções do domínio Customer."""


class CustomerNotFoundError(CustomerError):
    """User logado ainda não fez POST /customers (lazy creation, ADR-027 dec. 2)."""


class CustomerAlreadyExistsError(CustomerError):
    """User logado já tem Customer cadastrado (ADR-027 dec. 4 — POST 409)."""


# === Operações ===


def get_customer_for_user(session: Session, user: User) -> Customer:
    """Retorna Customer do User logado.

    Raises:
        CustomerNotFoundError: User ainda não fez POST /customers.
    """
    customer = customer_repository.get_by_user_id(session, user.id)
    if customer is None:
        raise CustomerNotFoundError(
            "Customer não cadastrado. Use POST /api/v1/customers para criar."
        )
    return customer


def create_customer_for_user(
    session: Session,
    user: User,
    payload: CustomerCreate,
) -> Customer:
    """Cria Customer pro User logado.

    Phone vem de `user.phone` automaticamente (ADR-027 dec. 6 — garante
    User.phone == Customer.phone, sem cliente digitar 2 vezes).

    Raises:
        CustomerAlreadyExistsError: User já tem Customer (ADR-027 dec. 4 — 409).
    """
    existing = customer_repository.get_by_user_id(session, user.id)
    if existing is not None:
        raise CustomerAlreadyExistsError(
            f"Customer já cadastrado para este usuário (id={existing.id}). "
            "Use PATCH /api/v1/customers/me para atualizar."
        )

    customer = Customer(
        user_id=user.id,
        phone=user.phone,  # ADR-027 dec. 6
        name=payload.name,
        email=payload.email,
        cpf=payload.cpf,
        birth_date=payload.birth_date,
    )
    return customer_repository.create(session, customer)


def update_customer_for_user(
    session: Session,
    user: User,
    payload: CustomerUpdate,
) -> Customer:
    """Atualiza Customer do User logado (ADR-027 dec. 5).

    Apenas campos permitidos: name, email, cpf, birth_date.
    Pattern Pydantic v2 `exclude_unset=True` (ADR-027 dec. 8): distingue
    "campo não enviado" (mantém atual) de "campo enviado como null" (limpa).

    Raises:
        CustomerNotFoundError: User ainda não fez POST /customers.
    """
    customer = get_customer_for_user(session, user)

    # exclude_unset=True: só pega campos que o cliente realmente enviou.
    # Diferença crucial: {"email": None} no JSON limpa o email; omitir
    # email no JSON mantém o valor atual.
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(customer, field, value)

    session.flush()
    session.refresh(customer)
    return customer
