"""Testes das dependencies do FastAPI (ADR-020 layer: api)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt as jose_jwt
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_sms_provider
from app.core.config import get_settings
from app.models.user import User
from app.services.auth.jwt import JWT_ALGORITHM, create_access_token
from app.services.sms.base import SMSProviderConfigError
from app.services.sms.mock import MockSMSProvider


class TestGetSmsProvider:
    def setup_method(self) -> None:
        # Invalida caches entre casos (get_settings + get_sms_provider)
        get_settings.cache_clear()
        get_sms_provider.cache_clear()

    def teardown_method(self) -> None:
        get_settings.cache_clear()
        get_sms_provider.cache_clear()

    def test_returns_mock_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMS_PROVIDER", "mock")
        monkeypatch.setenv("APP_ENV", "local")

        provider = get_sms_provider()

        assert isinstance(provider, MockSMSProvider)

    def test_raises_on_unknown_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMS_PROVIDER", "foobar")

        with pytest.raises(SMSProviderConfigError, match="Unknown SMS_PROVIDER"):
            get_sms_provider()

    def test_is_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMS_PROVIDER", "mock")
        monkeypatch.setenv("APP_ENV", "local")

        p1 = get_sms_provider()
        p2 = get_sms_provider()

        assert p1 is p2


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestGetCurrentUser:
    def test_returns_user_for_valid_token(
        self,
        db_session: Session,
        authenticated_user: User,
    ) -> None:
        token = create_access_token(
            user_id=authenticated_user.id,
            phone=authenticated_user.phone,
        )

        result = get_current_user(credentials=_bearer(token), session=db_session)

        assert result.id == authenticated_user.id
        assert result.phone == authenticated_user.phone

    def test_raises_401_when_credentials_none(
        self,
        db_session: Session,
    ) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=None, session=db_session)

        assert exc_info.value.status_code == 401
        assert cast(dict[str, str], exc_info.value.detail)["code"] == "unauthenticated"

    def test_raises_401_token_expired_for_expired_jwt(
        self,
        db_session: Session,
        authenticated_user: User,
    ) -> None:
        settings = get_settings()
        past_exp = datetime.now(UTC) - timedelta(minutes=1)
        expired_token = jose_jwt.encode(
            {
                "sub": str(authenticated_user.id),
                "phone": authenticated_user.phone,
                "iat": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
                "exp": int(past_exp.timestamp()),
                "type": "access",
            },
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithm=JWT_ALGORITHM,
        )

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=_bearer(expired_token), session=db_session)

        assert exc_info.value.status_code == 401
        assert cast(dict[str, str], exc_info.value.detail)["code"] == "token_expired"

    def test_raises_401_invalid_token_for_malformed_jwt(
        self,
        db_session: Session,
    ) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=_bearer("not-a-jwt"), session=db_session)

        assert exc_info.value.status_code == 401
        assert cast(dict[str, str], exc_info.value.detail)["code"] == "invalid_token"

    def test_raises_401_invalid_token_when_user_not_in_db(
        self,
        db_session: Session,
    ) -> None:
        nonexistent_id = uuid.uuid4()
        token = create_access_token(user_id=nonexistent_id, phone="+5531999887766")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=_bearer(token), session=db_session)

        assert exc_info.value.status_code == 401
        assert cast(dict[str, str], exc_info.value.detail)["code"] == "invalid_token"
