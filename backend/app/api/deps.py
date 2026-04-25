"""Dependências compartilhadas do FastAPI (ADR-020 layer: api)."""

import logging
from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.errors import ErrorCode
from app.core.config import get_settings
from app.db.session import create_session
from app.models.user import User
from app.services.auth.jwt import (
    ExpiredTokenError,
    MalformedTokenError,
    decode_access_token,
)
from app.services.sms.base import SMSProvider, SMSProviderConfigError
from app.services.sms.mock import MockSMSProvider

logger = logging.getLogger(__name__)

# auto_error=False: deixa credentials=None se header ausente, permitindo
# retornar 401 unauthenticated em vez do 403 padrão do HTTPBearer (RFC 7235).
_security = HTTPBearer(auto_error=False)


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


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_security)],
    session: Annotated[Session, Depends(get_db_session)],
) -> User:
    """Decodifica JWT do header Authorization e retorna User autenticado (ADR-025).

    Cenários de 401:
    - Header Authorization ausente OU sem prefixo "Bearer " → unauthenticated
    - JWT expirado (exp < now) → token_expired (sem log — fluxo normal)
    - JWT malformado, assinatura inválida, claims faltando → invalid_token + log WARNING
    - Token válido mas user_id do sub não existe no banco → invalid_token + log WARNING

    Diferenciação token_expired vs invalid_token: token_expired é estado
    funcional normal (acontece a cada 60min). invalid_token sinaliza
    possível vetor de ataque ou bug do cliente — merece log de segurança.

    Header WWW-Authenticate: Bearer em todas as 401 (RFC 6750 compliance).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.UNAUTHENTICATED.value,
                "message": "Autenticação necessária. Faça login para continuar.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except ExpiredTokenError as exc:
        # Estado normal — sem log (acontece a cada 60min em uso real).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.TOKEN_EXPIRED.value,
                "message": "Sessão expirada. Faça login novamente.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except MalformedTokenError as exc:
        # Possível ataque ou bug — log WARNING como evento de segurança.
        logger.warning("auth.malformed_token error=%s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.INVALID_TOKEN.value,
                "message": "Token inválido.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = session.get(User, payload.user_id)
    if user is None:
        # Token assinado corretamente mas user_id não existe no banco.
        # Cenários: User foi deletado (futuro LGPD) ou token forjado por
        # alguém com acesso ao secret. Log WARNING.
        logger.warning("auth.user_not_found user_id=%s", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.INVALID_TOKEN.value,
                "message": "Token inválido.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
