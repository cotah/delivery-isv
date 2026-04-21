from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Naming convention conforme ADR-007.
# Força nomes consistentes em PKs, FKs, uniques, checks e índices.
NAMING_CONVENTION: dict[str, str] = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos ORM do ISV Delivery.

    Aplica a naming_convention definida no ADR-007 automaticamente
    a todas as constraints e índices gerados pelo SQLAlchemy/Alembic.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
