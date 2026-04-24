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
    SMS_PROVIDER_ERROR = "sms_provider_error"
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
) -> JSONResponse:
    """Monta JSONResponse com formato uniforme do ADR-022."""
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


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
    return _build_response(exc.status_code, code, message)


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
