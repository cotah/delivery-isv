"""JWT access token — criação e decodificação (ADR-025 decisão 7).

Algoritmo HS256 com secret simétrico de 64 bytes (>=256 bits de entropia).
Claims: sub (user.id como string), phone (E.164), iat, exp, type="access".
Expiração: 60 minutos (configurável via JWT_EXPIRATION_MINUTES).

Sem refresh token no MVP (ADR-025 dívida técnica #4). Cliente refaz OTP
quando access expira.

Sem revogação em tempo real (ADR-025 dívida técnica #6). Rotação de
JWT_SECRET_KEY é mitigação aceitável no piloto (mass logout).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Base para falhas de decode de JWT access token."""


class ExpiredTokenError(InvalidTokenError):
    """Token expirado (exp < now).

    Middleware deve retornar 401 com mensagem amigável pro cliente
    refazer login via OTP.
    """


class MalformedTokenError(InvalidTokenError):
    """Token mal formado, assinatura inválida, ou claims faltando/inválidos.

    Middleware deve retornar 401 genérico e LOGAR como evento de
    segurança — possível tentativa de forjar ou bug no cliente.
    """


@dataclass(frozen=True)
class AccessTokenPayload:
    """Payload decodificado de um access token.

    Campos:
    - user_id: UUID do User (do claim 'sub')
    - phone: telefone E.164 (do claim 'phone')
    - issued_at: timestamp de criação do token
    - expires_at: timestamp de expiração
    - token_type: sempre "access" no CP3 (refresh vira em ciclo futuro)
    """

    user_id: UUID
    phone: str
    issued_at: datetime
    expires_at: datetime
    token_type: str


def create_access_token(user_id: UUID, phone: str) -> str:
    """Cria access token JWT assinado com HS256.

    Claims:
        sub: str(user_id)
        phone: phone E.164
        iat: datetime now UTC como Unix timestamp
        exp: iat + JWT_EXPIRATION_MINUTES
        type: "access"

    Args:
        user_id: UUID do User autenticado
        phone: telefone E.164 do User (pra auditoria em logs)

    Returns:
        JWT assinado como string.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)

    claims = {
        "sub": str(user_id),
        "phone": phone,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "type": "access",
    }

    token: str = jwt.encode(
        claims,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )
    return token


def decode_access_token(token: str) -> AccessTokenPayload:
    """Decodifica e valida access token JWT.

    Validações:
    - Assinatura bate com JWT_SECRET_KEY
    - exp > now (token não expirado)
    - Claims obrigatórios presentes: sub, phone, iat, exp, type
    - type == "access"
    - sub é UUID válido

    Args:
        token: string JWT recebida (tipicamente do header Authorization)

    Returns:
        AccessTokenPayload com campos validados.

    Raises:
        ExpiredTokenError: se exp < now
        MalformedTokenError: se formato, assinatura, claims ou type inválidos
    """
    settings = get_settings()

    try:
        claims = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise ExpiredTokenError("Token has expired") from exc
    except JWTError as exc:
        raise MalformedTokenError(f"Invalid token: {exc}") from exc

    required_claims = {"sub", "phone", "iat", "exp", "type"}
    missing = required_claims - set(claims.keys())
    if missing:
        raise MalformedTokenError(f"Missing required claims: {sorted(missing)}")

    if claims["type"] != "access":
        raise MalformedTokenError(f"Invalid token type: expected 'access', got {claims['type']!r}")

    try:
        user_id = UUID(claims["sub"])
    except (ValueError, TypeError) as exc:
        raise MalformedTokenError(f"Invalid 'sub' claim: {claims['sub']!r}") from exc

    return AccessTokenPayload(
        user_id=user_id,
        phone=claims["phone"],
        issued_at=datetime.fromtimestamp(claims["iat"], tz=UTC),
        expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
        token_type=claims["type"],
    )
