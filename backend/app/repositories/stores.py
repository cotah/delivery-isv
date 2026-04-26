"""Queries ORM de Store (ADR-020 layer: repository)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import StoreStatus
from app.models.store import Store


def list_active_stores(
    session: Session,
    offset: int,
    limit: int,
) -> tuple[list[Store], int]:
    """Lista lojas aprovadas e não-deletadas, paginadas.

    Filtros aplicados (ADR-024):
    - status = APPROVED
    - deleted_at IS NULL (ADR-004)

    Eager loading via selectinload (ADR-014, ADR-020) — evita N+1:
    - category: 1 query extra pelo batch inteiro
    - city: 1 query extra pelo batch inteiro

    Retorna:
    - items: lista de Store (com category e city populados)
    - total: count após filtros (independente de offset/limit)
    """
    base_filters = [
        Store.status == StoreStatus.APPROVED,
        Store.deleted_at.is_(None),
    ]

    items_stmt = (
        select(Store)
        .where(*base_filters)
        .options(
            selectinload(Store.category),
            selectinload(Store.city),
        )
        # Tiebreaker determinístico (Store.id) garante paginação estável mesmo com
        # múltiplos INSERTs na mesma transação (created_at idêntico via func.now()).
        .order_by(Store.created_at.desc(), Store.id.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.execute(items_stmt).scalars().all())

    total_stmt = select(func.count()).select_from(Store).where(*base_filters)
    total = session.execute(total_stmt).scalar_one()

    return items, total


def get_active_store(
    session: Session,
    store_id: UUID,
) -> Store | None:
    """Busca Store aprovada e não-deletada por UUID.

    Retorna None se:
    - UUID não existe no banco
    - Store existe mas status != APPROVED
    - Store foi soft-deletada (deleted_at IS NOT NULL)

    Segurança: não diferencia "nunca existiu" de "removida" — retorno None
    uniforme preserva opacidade do UUID (ADR-024).

    Eager load (ADR-014):
    - category, city: embeds de StoreDetail
    - opening_hours: lista de slots (ADR-026 dec. 1, CP1b). Sem essa eager
      load, lazy="raise" no model levanta InvalidRequestError no service
      (_build_store_detail acessa store.opening_hours).
    """
    stmt = (
        select(Store)
        .where(
            Store.id == store_id,
            Store.status == StoreStatus.APPROVED,
            Store.deleted_at.is_(None),
        )
        .options(
            selectinload(Store.category),
            selectinload(Store.city),
            selectinload(Store.opening_hours),
        )
    )
    return session.execute(stmt).scalar_one_or_none()
