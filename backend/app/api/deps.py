"""Dependências compartilhadas do FastAPI (ADR-020 layer: api)."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_session
from app.services.sms.base import SMSProvider, SMSProviderConfigError
from app.services.sms.mock import MockSMSProvider


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


@lru_cache(maxsize=1)
def get_sms_provider() -> SMSProvider:
    """Retorna instância do SMSProvider baseado em SMS_PROVIDER (ADR-025).

    Singleton via lru_cache — 1 instância por processo. Cache por Settings
    via get_settings() — em testes, usar dependency_override do FastAPI
    ou get_sms_provider.cache_clear() entre casos.

    Raises:
        SMSProviderConfigError: se SMS_PROVIDER desconhecido ou config
                                inválida pro provider selecionado.
    """
    settings = get_settings()
    provider_name = settings.SMS_PROVIDER

    if provider_name == "mock":
        return MockSMSProvider(app_env=settings.APP_ENV)

    raise SMSProviderConfigError(f"Unknown SMS_PROVIDER: {provider_name!r}. Valid options: 'mock'.")
