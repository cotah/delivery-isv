"""create_store_opening_hours_table

Revision ID: 9a74dcc91e93
Revises: b964b10e6672
Create Date: 2026-04-26 00:55:43.659416

Resolve HIGH debt #1 — CP1b (ADR-026 dec. 1).

Tabela `store_opening_hours` com 1 row por slot de horário:
- day_of_week segue Postgres EXTRACT(DOW): 0=domingo..6=sábado (ADR-026 reforço D1)
- Slot cruzando meia-noite: close_time < open_time (ADR-026 dec. 3)
- FK store_id ondelete=CASCADE (composição estrita, ADR-015)
- 2 CheckConstraint: day_of_week range + open != close
- UniqueConstraint composto (store_id, day_of_week, open_time) — protege duplicatas
  exatas, NÃO protege overlaps parciais (validação deferida pro painel admin —
  ADR-026 reforço D4 débito diferido).
- Index (store_id, day_of_week) acelera query "aberto agora?"

Banco vazio (0 stores) — sem data migration necessária.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a74dcc91e93'
down_revision: Union[str, Sequence[str], None] = 'b964b10e6672'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'store_opening_hours',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('open_time', sa.Time(), nullable=False),
        sa.Column('close_time', sa.Time(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('day_of_week >= 0 AND day_of_week <= 6', name=op.f('ck_store_opening_hours_day_of_week_valid_range')),
        sa.CheckConstraint('open_time != close_time', name=op.f('ck_store_opening_hours_open_time_close_time_different')),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], name=op.f('fk_store_opening_hours_store_id'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_store_opening_hours')),
        sa.UniqueConstraint('store_id', 'day_of_week', 'open_time', name='uq_store_opening_hours_store_id_day_of_week_open_time'),
    )
    op.create_index('ix_store_opening_hours_store_id_day_of_week', 'store_opening_hours', ['store_id', 'day_of_week'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_store_opening_hours_store_id_day_of_week', table_name='store_opening_hours')
    op.drop_table('store_opening_hours')
