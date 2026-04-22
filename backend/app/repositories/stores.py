"""Queries ORM de Store (ADR-020 layer: repository)."""

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
