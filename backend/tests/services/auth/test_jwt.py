"""Testes de JWT access token (ADR-025 decisão 7)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt as jose_jwt

from app.core.config import get_settings
from app.services.auth.jwt import (
    JWT_ALGORITHM,
    AccessTokenPayload,
    ExpiredTokenError,
    InvalidTokenError,
    MalformedTokenError,
    create_access_token,
    decode_access_token,
)


def _encode_with_claims(claims: dict[str, object]) -> str:
    """Helper: monta token com claims arbitrários (usa mesmo secret do app)."""
    settings = get_settings()
    return jose_jwt.encode(
        claims,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


class TestCreateAccessToken:
    def test_returns_string(self) -> None:
        token = create_access_token(uuid.uuid4(), "+5531999887766")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decodable_with_correct_secret(self) -> None:
        user_id = uuid.uuid4()
        phone = "+5531999887766"

        token = create_access_token(user_id, phone)
        payload = decode_access_token(token)

        assert payload.user_id == user_id
        assert payload.phone == phone
        assert payload.token_type == "access"

    def test_expiration_respects_jwt_expiration_minutes_setting(self) -> None:
        settings = get_settings()
        before = datetime.now(UTC)

        token = create_access_token(uuid.uuid4(), "+5531999887766")
        payload = decode_access_token(token)

        delta = payload.expires_at - payload.issued_at
        assert delta == timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
        # Issued_at fica próximo do momento da chamada (±5s pra latência do CI)
        assert abs((payload.issued_at - before).total_seconds()) < 5

    def test_different_users_produce_different_tokens(self) -> None:
        t1 = create_access_token(uuid.uuid4(), "+5531999887766")
        t2 = create_access_token(uuid.uuid4(), "+5531999887766")
        assert t1 != t2

    def test_type_claim_is_access(self) -> None:
        token = create_access_token(uuid.uuid4(), "+5531999887766")
        payload = decode_access_token(token)
        assert payload.token_type == "access"


class TestDecodeAccessToken:
    def test_decodes_valid_token(self) -> None:
        user_id = uuid.uuid4()
        phone = "+5531988776655"

        token = create_access_token(user_id, phone)
        payload = decode_access_token(token)

        assert isinstance(payload, AccessTokenPayload)
        assert payload.user_id == user_id
        assert payload.phone == phone

    def test_raises_expired_for_past_exp(self) -> None:
        past_exp = datetime.now(UTC) - timedelta(minutes=1)
        past_iat = datetime.now(UTC) - timedelta(hours=1)
        expired_token = _encode_with_claims(
            {
                "sub": str(uuid.uuid4()),
                "phone": "+5531999887766",
                "iat": int(past_iat.timestamp()),
                "exp": int(past_exp.timestamp()),
                "type": "access",
            }
        )

        with pytest.raises(ExpiredTokenError):
            decode_access_token(expired_token)

    def test_raises_malformed_for_random_string(self) -> None:
        with pytest.raises(MalformedTokenError):
            decode_access_token("not-a-jwt-at-all")

    def test_raises_malformed_for_empty_string(self) -> None:
        with pytest.raises(MalformedTokenError):
            decode_access_token("")

    def test_raises_malformed_for_wrong_signature(self) -> None:
        now = datetime.now(UTC)
        claims = {
            "sub": str(uuid.uuid4()),
            "phone": "+5531999887766",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=60)).timestamp()),
            "type": "access",
        }
        # Assinado com secret diferente — decode com nosso secret deve falhar
        bad_token = jose_jwt.encode(claims, "some-other-secret-xyz", algorithm=JWT_ALGORITHM)

        with pytest.raises(MalformedTokenError):
            decode_access_token(bad_token)

    def test_raises_malformed_for_missing_sub_claim(self) -> None:
        now = datetime.now(UTC)
        token = _encode_with_claims(
            {
                "phone": "+5531999887766",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=60)).timestamp()),
                "type": "access",
            }
        )

        with pytest.raises(MalformedTokenError, match="Missing required claims"):
            decode_access_token(token)

    def test_raises_malformed_for_missing_exp_claim(self) -> None:
        now = datetime.now(UTC)
        # jose preenche exp automaticamente se ausente? Não — só valida se presente.
        # Mas jose rejeita token sem exp via ExpiredSignatureError? Testa comportamento real.
        token = _encode_with_claims(
            {
                "sub": str(uuid.uuid4()),
                "phone": "+5531999887766",
                "iat": int(now.timestamp()),
                "type": "access",
            }
        )

        with pytest.raises(MalformedTokenError):
            decode_access_token(token)

    def test_raises_malformed_for_invalid_sub_uuid(self) -> None:
        now = datetime.now(UTC)
        token = _encode_with_claims(
            {
                "sub": "nao-eh-uuid",
                "phone": "+5531999887766",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=60)).timestamp()),
                "type": "access",
            }
        )

        with pytest.raises(MalformedTokenError, match="Invalid 'sub' claim"):
            decode_access_token(token)

    def test_raises_malformed_for_wrong_type_claim(self) -> None:
        now = datetime.now(UTC)
        token = _encode_with_claims(
            {
                "sub": str(uuid.uuid4()),
                "phone": "+5531999887766",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=60)).timestamp()),
                "type": "refresh",
            }
        )

        with pytest.raises(MalformedTokenError, match="Invalid token type"):
            decode_access_token(token)


class TestExceptionHierarchy:
    def test_expired_is_subclass_of_invalid_token(self) -> None:
        assert issubclass(ExpiredTokenError, InvalidTokenError)

    def test_malformed_is_subclass_of_invalid_token(self) -> None:
        assert issubclass(MalformedTokenError, InvalidTokenError)
