"""Rate limiting via slowapi + Redis (ADR-025 decisão 8).

CP3c implementa SOMENTE rate limit por IP (`get_remote_address`).
Settings declaram limites por phone (`RATE_LIMIT_*_PHONE`) mas eles
NÃO são aplicados nos decorators ainda — slowapi `key_func` é síncrono
e extrair phone do body exige body parsing assíncrono. Pattern previsto
em débito MEDIUM "Rate limit phone-based em endpoints Auth".

Fail-open quando Redis indisponível, em duas dimensões:

1. **Inicialização (startup):** se `Limiter(storage_uri=...)` levantar,
   try/except defensivo cai pra Limiter in-memory — app sobe vivo.

2. **Runtime (Redis cai DEPOIS do app subir):** slowapi flags
   `swallow_errors=True` + `in_memory_fallback_enabled=True` capturam
   `RedisError` no primeiro `.hit()`, marcam storage dead, transicionam
   pra in-memory automaticamente (rate limit per-process preservado),
   loga WARNING via logger `"slowapi"`. Auto-recovery quando Redis volta.

Princípio: app de delivery prioriza disponibilidade do login sobre
proteção 100% contra abuso temporário (ADR-022 + CP3c Auth D2).

Custom handler para 429 retorna formato canônico do projeto (ADR-022)
com `Retry-After` no header.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.errors import ErrorCode
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _build_limiter() -> Limiter:
    """Cria Limiter com storage_uri=REDIS_URL — fail-open em duas dimensões.

    RATE_LIMIT_ENABLED=False → Limiter inerte (slowapi vira no-op).
    Conexão Redis é lazy: slowapi conecta no primeiro request, não na
    instanciação — try/except aqui é defensivo (versões futuras de slowapi
    podem mudar o comportamento). Se a instanciação falhar por motivo
    inesperado, fallback para Limiter in-memory: requests passam, contagem
    perde estado entre restarts. Login mantido vivo (ADR-025 decisão 8).

    Runtime fail-open (Redis cai DEPOIS do app subir) coberto pelas flags
    `swallow_errors=True` + `in_memory_fallback_enabled=True` — slowapi
    captura `RedisError` no `.hit()`, marca `_storage_dead=True`,
    transiciona pra in-memory transparente. Auto-recovery via
    `_storage.check()` periódico quando Redis volta. Log WARNING emitido
    pelo logger `"slowapi"` (propaga pra root — captura via Sentry/Datadog
    quando observability entrar).
    """
    settings = get_settings()

    if not settings.RATE_LIMIT_ENABLED:
        logger.info("rate_limit.disabled via RATE_LIMIT_ENABLED=false")
        return Limiter(key_func=get_remote_address, enabled=False)

    try:
        return Limiter(
            key_func=get_remote_address,
            storage_uri=settings.REDIS_URL,
            default_limits=[],
            swallow_errors=True,  # fail-open runtime — ADR-022 + CP3c Auth D2
            in_memory_fallback_enabled=True,  # proteção residual durante outage Redis
        )
    except Exception as exc:
        # Fail-open: sem storage Redis, slowapi cai pra in-memory.
        # Alerta vira automático quando observability (Sentry/Datadog)
        # entrar — debito de ciclo futuro.
        logger.warning(
            "rate_limit.redis_init_failed error=%s fallback=memory_only",
            str(exc),
        )
        return Limiter(key_func=get_remote_address)


limiter = _build_limiter()


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Handler 429 retornando formato ErrorResponse do projeto (ADR-022).

    Retry-After header presente — clientes (frontend) leem pra agendar retry.
    """
    # slowapi expõe o limit info via exc.detail — usa retry_after default
    # de 1 hora (limites atuais são todos /hour).
    retry_after_seconds = 3600

    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": ErrorCode.RATE_LIMITED.value,
                "message": "Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.",
                "retry_after_seconds": retry_after_seconds,
            }
        },
        headers={"Retry-After": str(retry_after_seconds)},
    )
