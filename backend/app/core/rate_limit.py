"""Rate limiting via slowapi + Redis (ADR-025 decisão 8).

Defesa em duas camadas:

1. **Por IP** (decorator `@limiter.limit(...)`): slowapi nativo,
   `key_func=get_remote_address`. Roda ANTES do body do endpoint.
   Anti-scrape (multi-phone vindo do mesmo IP).

2. **Por phone** (helper `check_phone_rate_limit(...)`): chamado
   manualmente no endpoint APÓS Pydantic parsear+validar o payload
   (phone garantido em E.164 canônico). Anti-targeted-abuse (mesmo
   phone vindo de múltiplos IPs). Slowapi `key_func` é síncrono e
   sem acesso ao body — manual hit é a única opção viável.

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
from limits import parse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit

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


def _make_phone_limit(limit_str: str) -> Limit:
    """Wrapper minimal pra `slowapi.wrappers.Limit` (ctor exige 9 args).

    Usado APENAS pra raise `RateLimitExceeded(limit)` — handler
    `rate_limit_exceeded_handler` lê `exc.detail` mas ignora pra usar
    formato canônico do projeto. key_func/scope/exempt_when/etc não
    são consultados nesse path.
    """
    return Limit(
        limit=parse(limit_str),
        key_func=lambda: "phone",
        scope=None,
        per_method=False,
        methods=None,
        error_message=None,
        exempt_when=None,
        cost=1,
        override_defaults=False,
    )


def check_phone_rate_limit(*, scope: str, phone: str, limit_str: str) -> None:
    """Aplica rate limit por phone como SEGUNDA camada, após decorator IP.

    Defesa em camadas (ADR-022 + CP3c Auth D2):
    1. `@limiter.limit(IP)` — anti-scrape, roda ANTES (decorator slowapi).
    2. `check_phone_rate_limit(phone)` — anti-targeted-abuse (esta função).

    Phone DEVE chegar normalizado E.164 (formato canônico só com digits
    e leading `+`). `validate_phone_e164` (chamado por Pydantic
    `field_validator` em `app/schemas/auth.py`) garante isso na borda —
    variantes com whitespace/dashes recebem 422 antes deste helper rodar.

    Fail-open replicado manualmente: slowapi flag `swallow_errors=True`
    aplica APENAS ao `_check_request_limit` interno (chamado pelos
    decorators `@limiter.limit`). Chamada manual a `limiter.limiter.hit()`
    bypassa essa lógica — sem este try/except, queda do Redis viraria
    500 nos endpoints Auth, regredindo o ganho do MEDIUM #3 (resolvido
    em 2026-04-26 via swallow_errors+in_memory_fallback).

    Args:
        scope: namespace do endpoint (ex: "request-otp", "verify-otp").
            Separa contadores entre endpoints — mesmo phone com OTPs
            diferentes não bate limites cruzados.
        phone: telefone E.164 canônico (validate_phone_e164 garante).
        limit_str: limite no formato slowapi/limits (ex: "3/hour").

    Raises:
        RateLimitExceeded: phone excedeu o limit. Handler customizado
            (`rate_limit_exceeded_handler`) traduz pra 429 ADR-022.
    """
    if not limiter.enabled:
        return

    phone_limit = _make_phone_limit(limit_str)
    # Identifiers: namespace por scope evita colisão entre endpoints.
    # Resultado Redis key: LIMITS/phone:request-otp/+5531999887766/<window>
    identifiers = (f"phone:{scope}", phone)

    try:
        if not limiter.limiter.hit(phone_limit.limit, *identifiers, cost=1):
            raise RateLimitExceeded(phone_limit)
    except RateLimitExceeded:
        raise
    except Exception as exc:
        # Fail-open: igual ao MEDIUM #3 (CP3c Auth D2). swallow_errors
        # do slowapi NÃO cobre hit manual — replicar pattern aqui.
        logger.warning(
            "phone_rate_limit.storage_unreachable scope=%s error=%s",
            scope,
            str(exc),
        )
