"""seed mg cities

Revision ID: ffd2034a50bd
Revises: 57aa2a205690
Create Date: 2026-04-21 14:41:16.926084

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ffd2034a50bd"
down_revision: Union[str, Sequence[str], None] = "57aa2a205690"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Lightweight table definition — não importa do modelo pra
# proteger a migration contra mudanças futuras nos modelos.
cities_table = sa.table(
    "cities",
    sa.column("name", sa.String),
    sa.column("state", sa.String),
    sa.column("slug", sa.String),
)


def upgrade() -> None:
    """Seed das 3 cidades piloto de Minas Gerais."""
    op.bulk_insert(
        cities_table,
        [
            {"name": "Tarumirim", "state": "MG", "slug": "tarumirim-mg"},
            {"name": "Itanhomi", "state": "MG", "slug": "itanhomi-mg"},
            {"name": "Alvarenga", "state": "MG", "slug": "alvarenga-mg"},
        ],
    )


def downgrade() -> None:
    """Remove as 3 cidades piloto (por slug — idempotente)."""
    op.execute(
        "DELETE FROM cities WHERE slug IN "
        "('tarumirim-mg', 'itanhomi-mg', 'alvarenga-mg')"
    )
