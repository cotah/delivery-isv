"""Fixtures compartilhadas de teste.

- `db_session`: Session SQLAlchemy com rollback automático por teste.
  Isola cada teste via connection + transaction + rollback — nada é persistido.
- `client`: TestClient FastAPI com dependency_override de `get_db_session`,
  garantindo que o endpoint usa a mesma session do teste.
- Factories (`city_factory`, `category_factory`, `store_factory`): criam
  registros mínimos válidos pra testes de repositório/endpoint.
"""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.db.session import get_engine
from app.main import app
from tests.utils.tax_id import generate_valid_cnpj


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Session de DB com rollback automático por teste.

    Usa connection + transaction explícita + rollback no final
    pra garantir isolamento entre testes. Requer que migrations
    já tenham rodado (alembic upgrade head) no banco de teste.
    """
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient com override de get_db_session pra usar db_session fixture.

    Garante que o endpoint usa a mesma session que o teste,
    com rollback automático.
    """

    def _override_get_db_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def city_factory(db_session: Session) -> Any:
    """Cria uma City válida (MG) pra testes."""
    from app.models.city import City

    def _create(**overrides: Any) -> City:
        suffix = uuid.uuid4().hex[:6]
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "name": f"Cidade Teste {suffix}",
            "state": "MG",
            "slug": f"cidade-teste-{suffix}",
            "is_active": True,
        }
        defaults.update(overrides)
        city = City(**defaults)
        db_session.add(city)
        db_session.flush()
        return city

    return _create


@pytest.fixture
def category_factory(db_session: Session) -> Any:
    """Cria uma Category pra testes."""
    from app.models.category import Category

    def _create(**overrides: Any) -> Category:
        suffix = uuid.uuid4().hex[:6]
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "name": f"Categoria {suffix}",
            "slug": f"cat-{suffix}",
            "is_active": True,
        }
        defaults.update(overrides)
        cat = Category(**defaults)
        db_session.add(cat)
        db_session.flush()
        return cat

    return _create


@pytest.fixture
def store_factory(
    db_session: Session,
    city_factory: Any,
    category_factory: Any,
) -> Any:
    """Cria uma Store pra testes. Status default APPROVED.

    Cobre todos os NOT NULLs reais do Store (legal_name/trade_name/tax_id/
    tax_id_type/slug/street/number/neighborhood/zip_code/status/FKs).
    tax_id gerado por generate_valid_cnpj pra satisfazer UNIQUE + @validates.
    """
    from app.domain.enums import StoreStatus, TaxIdType
    from app.models.store import Store

    def _create(**overrides: Any) -> Store:
        suffix = uuid.uuid4().hex[:6]
        city = overrides.pop("city", None) or city_factory()
        category = overrides.pop("category", None) or category_factory()

        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "legal_name": f"Teste Store LTDA {suffix}",
            "trade_name": f"Store {suffix}",
            "tax_id": generate_valid_cnpj(),
            "tax_id_type": TaxIdType.CNPJ,
            "slug": f"store-{suffix}",
            "street": "Rua Teste",
            "number": "123",
            "neighborhood": "Centro",
            "zip_code": "35855000",
            "status": StoreStatus.APPROVED,
            "city_id": city.id,
            "category_id": category.id,
        }
        defaults.update(overrides)
        store = Store(**defaults)
        db_session.add(store)
        db_session.flush()
        return store

    return _create
