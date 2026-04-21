from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.mixins import CreatedAtMixin, SoftDeleteMixin, TimestampMixin


class _TestBase(DeclarativeBase):
    """Base isolada para tests — não polui Base.metadata da aplicação."""


class _FullModel(_TestBase, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "_full_mixin_model"

    id: Mapped[int] = mapped_column(primary_key=True)


class _LogModel(_TestBase, CreatedAtMixin):
    __tablename__ = "_log_mixin_model"

    id: Mapped[int] = mapped_column(primary_key=True)


def test_timestamp_mixin_has_created_at_and_updated_at() -> None:
    cols = _FullModel.__table__.columns
    assert "created_at" in cols
    assert "updated_at" in cols


def test_timestamp_mixin_columns_are_timestamptz() -> None:
    created_type = _FullModel.__table__.columns["created_at"].type
    updated_type = _FullModel.__table__.columns["updated_at"].type
    assert isinstance(created_type, DateTime)
    assert isinstance(updated_type, DateTime)
    assert created_type.timezone is True
    assert updated_type.timezone is True


def test_timestamp_mixin_columns_are_not_nullable() -> None:
    cols = _FullModel.__table__.columns
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False


def test_timestamp_mixin_has_server_default_and_onupdate() -> None:
    cols = _FullModel.__table__.columns
    assert cols["created_at"].server_default is not None
    assert cols["updated_at"].server_default is not None
    assert cols["updated_at"].onupdate is not None


def test_soft_delete_mixin_has_nullable_deleted_at() -> None:
    deleted_col = _FullModel.__table__.columns["deleted_at"]
    assert deleted_col.nullable is True
    assert isinstance(deleted_col.type, DateTime)
    assert deleted_col.type.timezone is True


def test_created_at_mixin_only_has_created_at() -> None:
    cols = _LogModel.__table__.columns
    assert "created_at" in cols
    assert "updated_at" not in cols
    assert "deleted_at" not in cols
