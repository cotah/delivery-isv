"""add_status_to_product_variation

Revision ID: 661195884f97
Revises: 2e0d02f42dab
Create Date: 2026-04-25 14:37:39.631237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '661195884f97'
down_revision: Union[str, Sequence[str], None] = '2e0d02f42dab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'product_variations',
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
    )
    # CHECK constraint não detectada pelo autogenerate em ADD COLUMN — adicionada manualmente.
    # Espelha _VARIATION_STATUS_CHECK em app/models/product_variation.py (ADR-006).
    op.create_check_constraint(
        'ck_product_variations_status',
        'product_variations',
        "status IN ('active', 'inactive')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_product_variations_status', 'product_variations', type_='check')
    op.drop_column('product_variations', 'status')
