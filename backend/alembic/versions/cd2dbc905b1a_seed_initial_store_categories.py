"""seed initial store categories

Revision ID: cd2dbc905b1a
Revises: 5bef01ffe1ab
Create Date: 2026-04-21 16:44:06.225778

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "cd2dbc905b1a"
down_revision: Union[str, Sequence[str], None] = "5bef01ffe1ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Lightweight table definition — não importa do modelo pra
# proteger a migration contra mudanças futuras nos modelos.
categories_table = sa.table(
    "categories",
    sa.column("name", sa.String),
    sa.column("slug", sa.String),
)


def upgrade() -> None:
    """Seed inicial de categorias de Store (ADR-013).

    Valores pro piloto Tarumirim. Novas categorias serão adicionadas
    pelo admin via painel conforme a plataforma cresce.
    """
    op.bulk_insert(
        categories_table,
        [
            {"name": "Pizzaria", "slug": "pizzaria"},
            {"name": "Lanchonete", "slug": "lanchonete"},
            {"name": "Marmita", "slug": "marmita"},
        ],
    )


def downgrade() -> None:
    """Remove as 3 categorias iniciais (idempotente por slug)."""
    op.execute(
        "DELETE FROM categories WHERE slug IN "
        "('pizzaria', 'lanchonete', 'marmita')"
    )
