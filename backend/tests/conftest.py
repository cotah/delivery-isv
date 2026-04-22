"""Fixtures compartilhadas de teste.

- `db_session`: Session SQLAlchemy com rollback automático por teste.
  Isola cada teste via SAVEPOINT/rollback — nada é persistido.
- `client`: TestClient FastAPI com dependency_override de `get_db_session`,
  garantindo que o endpoint usa a mesma session do teste.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.db.session import get_engine
from app.main import app


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
