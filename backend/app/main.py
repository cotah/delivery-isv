from typing import Any, cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.errors import http_exception_handler, validation_exception_handler
from app.api.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

app = FastAPI(
    title="ISV Delivery API",
    version=__version__,
)

# Rate limiter singleton (ADR-025 decisão 8). slowapi exige app.state.limiter.
app.state.limiter = limiter

# CORS aberto para dev local. Produção terá allow_origins específico por ambiente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers uniformes (ADR-022) — ativos em todas as rotas, inclusive /health.
# Starlette's add_exception_handler types the handler parameter as
# Callable[[Request, Exception], ...] instead of using a TypeVar bound
# to Exception, which means specific subclasses (StarletteHTTPException,
# RequestValidationError) fail mypy strict. Upstream limitation — see:
# https://github.com/encode/starlette/discussions/2416
# Cast isolates the workaround here; handlers in app/api/errors.py keep
# honest typing (StarletteHTTPException, RequestValidationError).
app.add_exception_handler(StarletteHTTPException, cast(Any, http_exception_handler))
app.add_exception_handler(RequestValidationError, cast(Any, validation_exception_handler))
app.add_exception_handler(RateLimitExceeded, cast(Any, rate_limit_exceeded_handler))

app.include_router(health_router)
app.include_router(api_v1_router)
