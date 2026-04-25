"""add_display_order_menu_section_featured

Revision ID: 90b06a960788
Revises: 661195884f97
Create Date: 2026-04-25 15:40:04.386310

Resolve HIGH debt #2 (Organização do cardápio):
- Product ganha display_order, menu_section, featured
- Category ganha display_order
- Rows existentes: display_order populado sequencialmente via ROW_NUMBER()
  OVER (ORDER BY created_at) — global em categories, PARTITION BY store_id
  em products (Product não tem category_id; ordenação independente por loja)
- Rows existentes: menu_section recebe 'other' via server_default (lojista
  reorganiza depois pelo painel)
- Rows existentes: featured recebe false via server_default

CHECK constraint pra menu_section adicionada manualmente — alembic
autogenerate não detecta CheckConstraint em ADD COLUMN (pattern já
visto no commit 3159442 do CP1 HIGH).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90b06a960788'
down_revision: Union[str, Sequence[str], None] = '661195884f97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ADD COLUMN — autogenerate ok.
    op.add_column(
        'categories',
        sa.Column('display_order', sa.Integer(), server_default='0', nullable=False),
    )
    op.add_column(
        'products',
        sa.Column('display_order', sa.Integer(), server_default='0', nullable=False),
    )
    op.add_column(
        'products',
        sa.Column('menu_section', sa.String(length=20), server_default='other', nullable=False),
    )
    op.add_column(
        'products',
        sa.Column('featured', sa.Boolean(), server_default='false', nullable=False),
    )

    # CheckConstraint pra menu_section — autogenerate não detecta em ADD COLUMN.
    # Espelha _PRODUCT_MENU_SECTION_CHECK em app/models/product.py (ADR-006).
    # Passamos só 'menu_section' (sufixo) — naming_convention prefixa com
    # 'ck_<table>_' resultando em 'ck_products_menu_section' no DB. Evita
    # prefixo duplicado tipo 'ck_products_ck_products_menu_section' que
    # acontece quando se passa o nome completo.
    op.create_check_constraint(
        'menu_section',
        'products',
        (
            "menu_section IN ("
            "'appetizer', 'snack', 'pizza', 'main_course', 'side_dish', "
            "'beverage', 'dessert', 'combo', 'other'"
            ")"
        ),
    )

    # Popular display_order sequencial por created_at (D3 aprovado).
    # Categories: ordem global (3 rows seed: pizzaria, lanchonete, marmita).
    # No-op se não há rows — UPDATE com subquery vazia executa sem erro.
    op.execute(
        """
        UPDATE categories SET display_order = subq.row_num
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) AS row_num
            FROM categories
        ) subq
        WHERE categories.id = subq.id
        """
    )

    # Products: PARTITION BY store_id (cada loja numera o próprio menu).
    # Decisão crítica do PASSO 0: Product não tem category_id, então PARTITION
    # BY store_id é o agrupamento natural (menu de cada loja é independente).
    # Em prod local (0 products) é no-op limpo — SQL valida sintaxe + cobre
    # caso "se houvesse rows" sem precisar fixture artificial.
    op.execute(
        """
        UPDATE products SET display_order = subq.row_num
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY store_id ORDER BY created_at
            ) AS row_num
            FROM products
        ) subq
        WHERE products.id = subq.id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Mesmo pattern do upgrade: passar sufixo, naming_convention prefixa.
    op.drop_constraint('menu_section', 'products', type_='check')
    op.drop_column('products', 'featured')
    op.drop_column('products', 'menu_section')
    op.drop_column('products', 'display_order')
    op.drop_column('categories', 'display_order')
