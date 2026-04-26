"""Repository de Customer (ADR-020 layer: repository, ADR-027)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer


def get_by_user_id(session: Session, user_id: UUID) -> Customer | None:
    """Busca Customer ativo (não soft-deletado) associado ao User.

    Filtros aplicados:
    - user_id == argumento (UNIQUE FK garante 0 ou 1 row)
    - deleted_at IS NULL (ADR-004 — soft-delete não bloqueia novo cadastro)

    Retorna None se:
    - User ainda não fez POST /customers (lazy creation, ADR-027 dec. 2)
    - Customer foi soft-deletado (anonimização LGPD futura)

    Reusado em GET /customers/me (retorna 404 se None), POST /customers
    (verifica conflict 409 se já existe), PATCH /customers/me (404 se None).
    """
    stmt = select(Customer).where(
        Customer.user_id == user_id,
        Customer.deleted_at.is_(None),
    )
    return session.execute(stmt).scalar_one_or_none()


def create(session: Session, customer: Customer) -> Customer:
    """Persiste Customer novo. Caller monta a instância (service layer).

    Assume que duplicate-check já foi feito antes (service chama
    get_by_user_id pra raise CustomerAlreadyExistsError pre-flush).
    Se algum dia houver race condition (2 POSTs concorrentes do mesmo
    User), o UNIQUE constraint em user_id no banco bloqueia o segundo
    via IntegrityError — caller deve traduzir.
    """
    session.add(customer)
    session.flush()
    session.refresh(customer)
    return customer
