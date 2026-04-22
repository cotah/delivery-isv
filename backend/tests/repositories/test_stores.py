"""Testes do repositório Store — comportamento do list_active_stores."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.enums import StoreStatus
from app.repositories import stores as stores_repository


class TestListActiveStores:
    def test_returns_only_approved(
        self,
        db_session: Session,
        store_factory: Any,
    ) -> None:
        store_factory(status=StoreStatus.APPROVED)
        store_factory(status=StoreStatus.PENDING)
        store_factory(status=StoreStatus.REJECTED)

        items, total = stores_repository.list_active_stores(db_session, 0, 20)

        assert len(items) == 1
        assert total == 1
        assert items[0].status == StoreStatus.APPROVED

    def test_excludes_soft_deleted(
        self,
        db_session: Session,
        store_factory: Any,
    ) -> None:
        store = store_factory(status=StoreStatus.APPROVED)
        store.deleted_at = datetime.now(UTC)
        db_session.flush()

        items, total = stores_repository.list_active_stores(db_session, 0, 20)

        assert items == []
        assert total == 0

    def test_respects_offset_limit(
        self,
        db_session: Session,
        store_factory: Any,
    ) -> None:
        for _ in range(5):
            store_factory(status=StoreStatus.APPROVED)

        items, total = stores_repository.list_active_stores(db_session, 2, 2)

        assert len(items) == 2
        assert total == 5  # total reflete count, não página

    def test_eager_loads_category_and_city(
        self,
        db_session: Session,
        store_factory: Any,
    ) -> None:
        """N+1 protection: lazy='raise' em Store.category/city deve
        ser contornado por selectinload no repository.
        """
        store_factory(status=StoreStatus.APPROVED)

        items, _ = stores_repository.list_active_stores(db_session, 0, 20)

        # Acessar category/city sem lazy load — se selectinload não rodou,
        # lazy='raise' levanta InvalidRequestError.
        assert items[0].category is not None
        assert items[0].city is not None
        assert items[0].category.name is not None
        assert items[0].city.name is not None

    def test_empty_db_returns_empty_list(self, db_session: Session) -> None:
        items, total = stores_repository.list_active_stores(db_session, 0, 20)
        assert items == []
        assert total == 0

    def test_ordered_by_created_at_desc(
        self,
        db_session: Session,
        store_factory: Any,
    ) -> None:
        """Stores retornam em ordem cronológica decrescente.

        created_at precisa ser explícito: fixture db_session usa 1 transação
        por teste (SAVEPOINT+rollback), e func.now() retorna transaction_timestamp
        (ADR-005) — 3 INSERTs consecutivos ganhariam created_at idêntico e a
        ordem cairia no tiebreaker id.desc (UUID aleatório, não cronológico).
        """
        from datetime import UTC, datetime, timedelta

        base = datetime.now(UTC)
        s1 = store_factory(status=StoreStatus.APPROVED, created_at=base)
        s2 = store_factory(status=StoreStatus.APPROVED, created_at=base + timedelta(seconds=1))
        s3 = store_factory(status=StoreStatus.APPROVED, created_at=base + timedelta(seconds=2))

        items, _ = stores_repository.list_active_stores(db_session, 0, 20)

        assert items[0].id == s3.id
        assert items[1].id == s2.id
        assert items[2].id == s1.id
