"""Infra de session do SQLAlchemy (ADR-020 layer: db).

Fornece engine singleton + sessionmaker pra dependency injection do FastAPI.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Engine do SQLAlchemy, cacheado. Uma instância por processo."""
    settings = get_settings()
    return create_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    """SessionLocal factory, cacheado."""
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def create_session() -> Session:
    """Cria uma Session nova. Caller responsável pelo close."""
    return get_sessionmaker()()
