"""Repository de Address (ADR-020 layer: repository, ADR-027 dec. 8-10)."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.address import Address


def list_active_by_customer(session: Session, customer_id: UUID) -> list[Address]:
    """Lista addresses ativos (não soft-deletados) do customer.

    Ordenação: is_default DESC (default primeiro), depois created_at DESC
    (mais recente primeiro). UX consistente: cliente vê endereço default
    no topo, depois ordem cronológica reversa.
    """
    stmt = (
        select(Address)
        .where(
            Address.customer_id == customer_id,
            Address.deleted_at.is_(None),
        )
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    return list(session.execute(stmt).scalars().all())


def get_for_customer(
    session: Session,
    address_id: UUID,
    customer_id: UUID,
) -> Address | None:
    """Busca Address por id, scoped ao customer (ADR-027 — security).

    Retorna None se:
    - address_id não existe
    - Address pertence a outro customer (não diferencia "não existe" de
      "não é seu" — pattern UUID opacity, mesmo do GET /stores/{id})
    - Address foi soft-deletado

    Endpoint traduz None pra 404 ADDRESS_NOT_FOUND.
    """
    stmt = select(Address).where(
        Address.id == address_id,
        Address.customer_id == customer_id,
        Address.deleted_at.is_(None),
    )
    return session.execute(stmt).scalar_one_or_none()


def create(session: Session, address: Address) -> Address:
    """Persiste Address novo. Caller monta a instância (service layer).

    Service garante que customer existe + city existe + is_default
    foi tratado (clear_default_for_customer ANTES) antes de chamar create.
    """
    session.add(address)
    session.flush()
    session.refresh(address)
    return address


def update_address(session: Session, address: Address) -> Address:
    """Persiste mudanças no Address (caller já mutou via setattr no service).

    Não recebe campos individuais — service usa exclude_unset + setattr,
    aqui só faz flush+refresh pra retornar Address atualizado com
    timestamps frescos.
    """
    session.flush()
    session.refresh(address)
    return address


def soft_delete(session: Session, address: Address) -> None:
    """Soft delete (ADR-004): seta deleted_at = now()."""
    from datetime import UTC, datetime

    address.deleted_at = datetime.now(UTC)
    session.flush()


def clear_default_for_customer(
    session: Session,
    customer_id: UUID,
    exclude_address_id: UUID | None = None,
) -> None:
    """Set is_default=false em todos addresses ativos do customer.

    Helper pra ADR-027 dec. 8: antes de marcar um Address como default,
    desmarca os outros. UNIQUE parcial no banco protege race condition
    (2 requests concorrentes), mas o service deve fazer o swap explícito
    pra UX consistente.

    exclude_address_id: pula este id (útil em PATCH onde o próprio
    Address sendo atualizado é o novo default — não precisa setar
    false em si mesmo antes de set true).
    """
    stmt = (
        update(Address)
        .where(
            Address.customer_id == customer_id,
            Address.is_default.is_(True),
            Address.deleted_at.is_(None),
        )
        .values(is_default=False)
    )
    if exclude_address_id is not None:
        stmt = stmt.where(Address.id != exclude_address_id)
    session.execute(stmt)
    session.flush()
