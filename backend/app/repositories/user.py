"""Repository de User (ADR-020 layer: repository, ADR-025)."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User


def find_user_by_phone(session: Session, phone: str) -> User | None:
    """Busca User por phone (UNIQUE). None se não existe."""
    stmt = select(User).where(User.phone == phone)
    return session.execute(stmt).scalar_one_or_none()


def find_or_create_user(session: Session, phone: str) -> User:
    """Busca User por phone, cria se não existir (lazy creation, ADR-025 decisão 6).

    Pattern try/INSERT/except IntegrityError + retry SELECT trata race
    condition de 2 verify-otp concorrentes do mesmo phone novo:

    1. SELECT — se achou, retorna
    2. INSERT (via session.flush) — tenta criar
    3. IntegrityError (UNIQUE phone violado): outro request criou primeiro
       → rollback + SELECT novamente, retorna o User do outro request

    Args:
        session: SQLAlchemy session (caller gerencia commit)
        phone: phone E.164 validado

    Returns:
        User existente ou recém-criado.

    Raises:
        IntegrityError: se SELECT pós-rollback não encontrar User
                        (não deveria acontecer — bug real do sistema).
    """
    existing = find_user_by_phone(session, phone)
    if existing is not None:
        return existing

    user = User(phone=phone)
    session.add(user)
    try:
        session.flush()
        return user
    except IntegrityError:
        session.rollback()
        existing_after_race = find_user_by_phone(session, phone)
        if existing_after_race is None:
            raise
        return existing_after_race
