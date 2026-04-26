"""Testes do modelo User (ADR-025)."""

from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from tests.utils.phone import generate_valid_phone_e164


class TestUser:
    def test_create_user_with_valid_phone(
        self,
        db_session: Session,
        user_factory: Any,
    ) -> None:
        phone = generate_valid_phone_e164()
        user = user_factory(phone=phone)

        assert user.id is not None
        assert user.phone == phone
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_phone_must_be_unique(
        self,
        db_session: Session,
        user_factory: Any,
    ) -> None:
        phone = generate_valid_phone_e164()
        user_factory(phone=phone)

        with pytest.raises(IntegrityError):
            user_factory(phone=phone)

    def test_phone_without_plus_rejected(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            User(phone="5531999887766")

    def test_phone_with_letters_rejected(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            User(phone="+5531abc887766")

    def test_phone_too_short_rejected(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            User(phone="+55319")

    def test_phone_empty_rejected(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match="required"):
            User(phone="")

    def test_phone_stored_in_e164_format(
        self,
        db_session: Session,
        user_factory: Any,
    ) -> None:
        phone = "+5531988776655"
        user = user_factory(phone=phone)

        db_session.flush()
        db_session.refresh(user)
        assert user.phone == phone

    # NOTA: teste de updated_at on_update removido intencionalmente.
    # Fixture db_session compartilhada usa 1 connection + 1 transaction
    # externa com rollback no teardown. Nesse pattern, session.commit()
    # não fecha a transação do DB — func.now() retorna o mesmo
    # transaction_timestamp() em INSERT e UPDATE subsequentes, mesmo
    # separados por time.sleep().
    #
    # Consequência: impossível testar empiricamente onupdate=func.now()
    # sem fixture dedicada. Comportamento é garantido pelo SQLAlchemy/Postgres,
    # não por nossa lógica. Presença da coluna updated_at já é validada
    # em test_create_user_with_valid_phone.
    #
    # Pattern dos 14 modelos anteriores é idêntico — nenhum testa on_update.
    # Se fixture dedicada virar necessária (ciclo futuro), criar
    # db_session_committed com 2 transações reais via engine.begin() +
    # cleanup manual. Débito registrado no roadmap do vault (prioridade LOW).

    def test_repr_contains_id_and_phone(
        self,
        user_factory: Any,
    ) -> None:
        """LGPD: phone mascarado em logs (pattern Customer/Store).

        Resolvido como débito LOW pré-piloto (antes phone cru, agora
        mask_phone_for_log aplicado — formato +55*********55).
        """
        user = user_factory(phone="+5531988776655")
        text = repr(user)

        assert str(user.id) in text
        # Phone cru NÃO deve aparecer (LGPD)
        assert "+5531988776655" not in text
        # Mascara mask_phone_for_log: +55 + asteriscos + últimos 2 dígitos
        assert "+55*********55" in text
