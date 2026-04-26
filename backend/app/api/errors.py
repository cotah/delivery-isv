"""Formato de erro uniforme (ADR-022).

Exception handlers convertem Starlette HTTPException e Pydantic
RequestValidationError pro envelope canônico do projeto:

    {"error": {"code": "...", "message": "...", "details": [...]?}}

Registrado em app.main via app.add_exception_handler.
"""

from enum import StrEnum
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(StrEnum):
    """Códigos de erro machine-readable (ADR-022).

    Usados no campo `error.code` pra permitir tratamento
    específico no frontend sem parsear mensagem.
    Novos códigos adicionados conforme endpoints precisarem.
    """

    VALIDATION_FAILED = "validation_failed"
    NOT_FOUND = "not_found"
    STORE_NOT_FOUND = "store_not_found"
    CUSTOMER_NOT_FOUND = "customer_not_found"
    CUSTOMER_ALREADY_EXISTS = "customer_already_exists"
    ADDRESS_NOT_FOUND = "address_not_found"
    CITY_NOT_FOUND = "city_not_found"
    SMS_PROVIDER_ERROR = "sms_provider_error"
    INVALID_OTP_CODE = "invalid_otp_code"
    RATE_LIMITED = "rate_limited"
    UNAUTHENTICATED = "unauthenticated"
    TOKEN_EXPIRED = "token_expired"
    INVALID_TOKEN = "invalid_token"
    INTERNAL_ERROR = "internal_error"


class ErrorDetail(BaseModel):
    """Detalhe de erro estrutural (opcional)."""

    field: str | None = None
    message: str


class ErrorBody(BaseModel):
    """Corpo do erro (ADR-022)."""

    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    """Envelope de resposta de erro (ADR-022)."""

    error: ErrorBody


def _build_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Monta JSONResponse com formato uniforme do ADR-022.

    headers: propaga headers do HTTPException (ex: WWW-Authenticate em 401
    via RFC 6750). Default None preserva comportamento dos handlers existentes.
    """
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body, headers=headers)


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Converte HTTPException pro formato do ADR-022.

    Suporta 2 formas de `exc.detail`:
    - dict com keys 'code' e 'message': endpoint customizou o erro (code
      específico tipo 'store_not_found'). Usa direto.
    - qualquer outro valor: fallback pelo status_code (code_map) + detail
      serializado como string (preserva comportamento default do FastAPI).
    """
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        code = exc.detail["code"]
        message = exc.detail["message"]
    else:
        code_map = {
            404: ErrorCode.NOT_FOUND.value,
        }
        code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR.value)
        message = str(exc.detail) if exc.detail else "Erro desconhecido"
    # Preserva headers da HTTPException (ex: WWW-Authenticate em 401 RFC 6750).
    headers = dict(exc.headers) if exc.headers else None
    return _build_response(exc.status_code, code, message, headers=headers)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Converte ValidationError do Pydantic pro formato do ADR-022."""
    details = [
        {
            "field": ".".join(str(x) for x in err["loc"]),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return _build_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code=ErrorCode.VALIDATION_FAILED.value,
        message="Falha na validação dos dados enviados",
        details=details,
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Captura ValueError de @validates do SQLAlchemy (assignment).

    `@validates` roda em assignment direto (`Customer(cpf="abc")`) e sobe
    `ValueError` puro, NÃO `StatementError` (que seria envelope só pra
    erros no flush, ex: CHECK constraint do DB violado).

    Sem este handler, FastAPI default vira 500 — UX errada (payload
    inválido é 422, não bug do servidor). Cliente recebe mensagem opaca
    e abre ticket de suporte.

    Trade-off: bug genuíno raise `ValueError` programático também vira
    422. Mas mensagem do error fica no body — debug viável. No projeto
    atual, dos 16 raises de ValueError, 15 são validation (todos viram
    422 com mensagem útil); 1 é guard de programador inalcançável via
    API real (`is_store_open` naive datetime).

    Pattern descoberto durante mini-CP fix pós-Customer cycle (2026-04-26)
    via reprodução empírica — confirmado que ValueError sobe puro do
    construtor, não envelopado.
    """
    return _build_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code=ErrorCode.VALIDATION_FAILED.value,
        message=str(exc),
    )
