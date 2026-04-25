"""add_store_extension_fields

Revision ID: b964b10e6672
Revises: d9a8d7e19f52
Create Date: 2026-04-26 00:09:50.229884

Resolve HIGH debt #1 — CP1a (ADR-026):
- Store ganha description (Text), phone (String(20) NOT NULL), minimum_order_cents
  (Integer), cover_image (String(500)), logo (String(500))
- CheckConstraint NULL-safe pra minimum_order_cents (>= 0 ou NULL)

phone NOT NULL direto (Opção E do ADR-026 dec. 5) — banco vazio em
2026-04-26 (0 stores), não há rows pra preencher. Migration cirúrgica
em 1 step. Plano de remediação se aplicar em DB com dados está no ADR.

CHECK constraint adicionada manualmente — alembic autogenerate não
detecta CheckConstraint em ADD COLUMN (pattern conhecido dos commits
3159442/CP1 HIGH e 16e664d/CP2 HIGH). Nome 'minimum_order_cents_non_negative'
sem prefixo — naming_convention prefixa com 'ck_stores_' automaticamente
(pattern documentado pelo fix LOW b9e79c7).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b964b10e6672'
down_revision: Union[str, Sequence[str], None] = 'd9a8d7e19f52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. Banco vazio (0 stores) — phone NOT NULL direto (ADR-026 dec. 5)."""
    op.add_column('stores', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('stores', sa.Column('phone', sa.String(length=20), nullable=False))
    op.add_column('stores', sa.Column('minimum_order_cents', sa.Integer(), nullable=True))
    op.add_column('stores', sa.Column('cover_image', sa.String(length=500), nullable=True))
    op.add_column('stores', sa.Column('logo', sa.String(length=500), nullable=True))

    # CheckConstraint manual — autogenerate não detecta em ADD COLUMN.
    # Nome só sufixo (naming_convention prefixa pra ck_stores_minimum_order_cents_non_negative).
    op.create_check_constraint(
        'minimum_order_cents_non_negative',
        'stores',
        "minimum_order_cents IS NULL OR minimum_order_cents >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('minimum_order_cents_non_negative', 'stores', type_='check')
    op.drop_column('stores', 'logo')
    op.drop_column('stores', 'cover_image')
    op.drop_column('stores', 'minimum_order_cents')
    op.drop_column('stores', 'phone')
    op.drop_column('stores', 'description')
