"""Dependências compartilhadas do FastAPI (ADR-020 layer: api)."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import create_session


def get_db_session() -> Generator[Session, None, None]:
    """Dependency do FastAPI pra yield Session por request.

    Padrão oficial FastAPI: yield + try/finally garante close
    mesmo em exceção. Rollback de transação não é feito aqui
    — fica a cargo da service layer se precisar (a maioria
    dos endpoints GET não tem transação explícita).
    """
    session = create_session()
    try:
        yield session
    finally:
        session.close()
