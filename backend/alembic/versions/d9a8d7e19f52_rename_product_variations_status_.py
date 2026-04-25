"""rename_product_variations_status_constraint

Revision ID: d9a8d7e19f52
Revises: 90b06a960788
Create Date: 2026-04-25 16:31:38.280011

Cosmetic rename of CheckConstraint with duplicate prefix in DB.

Background:
- CP1 HIGH (migration 661195884f97, commit 3159442) created the
  status CHECK constraint on product_variations passing the
  already-prefixed name 'ck_product_variations_status' to
  op.create_check_constraint(). naming_convention then prefixed
  it again with 'ck_<table>_' resulting in the DB name
  'ck_product_variations_ck_product_variations_status'.
- CP2 HIGH (migration 90b06a960788, commit 16e664d) discovered
  the correct pattern: pass only the suffix (e.g. 'menu_section')
  and let naming_convention add the 'ck_<table>_' prefix.

Functional behavior is identical (same status IN ('active',
'inactive') rule). Only the constraint name in pg_constraint
changes — application code is untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9a8d7e19f52'
down_revision: Union[str, Sequence[str], None] = '90b06a960788'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename constraint with duplicate prefix to clean name.

    Background: CP1 HIGH (migration 661195884f97) created the constraint
    with name 'ck_product_variations_ck_product_variations_status' in DB
    due to passing an already-prefixed name to op.create_check_constraint().
    The project's naming_convention 'ck_%(table_name)s_%(constraint_name)s'
    adds the 'ck_<table>_' prefix automatically.

    Fix logic: naming_convention is always-on in this project. To target
    a specific final name, pass the value 'one level below' so alembic
    adds the prefix to construct it.

    To DROP buggy 'ck_product_variations_ck_product_variations_status':
    pass 'ck_product_variations_status' -> naming_convention prefixes
    -> reconstructs the buggy duplicate-prefix name -> drops it.

    To CREATE clean 'ck_product_variations_status':
    pass 'status' (suffix only) -> naming_convention prefixes -> clean.
    """
    op.drop_constraint(
        # naming_convention prefixes -> reconstructs buggy duplicate-prefix name in DB.
        'ck_product_variations_status',
        'product_variations',
        type_='check',
    )
    op.create_check_constraint(
        # naming_convention prefixes -> ck_product_variations_status (clean).
        'status',
        'product_variations',
        "status IN ('active', 'inactive')",
    )


def downgrade() -> None:
    """Restore the duplicate-prefix name (matches CP1 HIGH original state).

    Mirror of upgrade() — also subject to naming_convention always-on.
    """
    op.drop_constraint(
        # naming_convention prefixes -> ck_product_variations_status (clean name from upgrade()).
        'status',
        'product_variations',
        type_='check',
    )
    op.create_check_constraint(
        # naming_convention prefixes -> reconstructs buggy duplicate-prefix name.
        'ck_product_variations_status',
        'product_variations',
        "status IN ('active', 'inactive')",
    )
