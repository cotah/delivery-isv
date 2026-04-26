"""add_user_id_fk_to_customers

Revision ID: 64f6e6cef194
Revises: 9a74dcc91e93
Create Date: 2026-04-26 02:13:01.484119

Resolve conexão User ↔ Customer (ADR-027 dec. 1, CP1 do ciclo Customer).

- ADD COLUMN user_id UUID NOT NULL (Opção E direto — banco vazio confirmado:
  0 customers, 0 users — sem placeholder)
- ADD UNIQUE CONSTRAINT uq_customers_user_id (1:1 garantido no banco)
- ADD FOREIGN KEY fk_customers_user_id ON DELETE RESTRICT (preserva
  histórico Order via Customer — pattern ADR-011)

User pode existir sem Customer (login OTP feito mas cadastro pendente —
lazy creation via POST /customers, ADR-027 dec. 2). Customer
obrigatoriamente tem 1 User.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64f6e6cef194'
down_revision: Union[str, Sequence[str], None] = '9a74dcc91e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. Banco vazio (0 customers, 0 users) — user_id NOT NULL direto."""
    op.add_column('customers', sa.Column('user_id', sa.Uuid(), nullable=False))
    op.create_unique_constraint(op.f('uq_customers_user_id'), 'customers', ['user_id'])
    op.create_foreign_key(
        op.f('fk_customers_user_id'),
        'customers',
        'users',
        ['user_id'],
        ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('fk_customers_user_id'), 'customers', type_='foreignkey')
    op.drop_constraint(op.f('uq_customers_user_id'), 'customers', type_='unique')
    op.drop_column('customers', 'user_id')
