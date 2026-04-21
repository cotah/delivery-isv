from typing import Annotated
from uuid import UUID

from sqlalchemy import Uuid, text
from sqlalchemy.orm import mapped_column

from app.db.identifiers import new_uuid

# Type alias para Primary Key UUID.
# Aplica ADR-003: Python default (testabilidade) + server_default
# Postgres (INSERT SQL direto, seeds, bulk operations).
UUIDPK = Annotated[
    UUID,
    mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    ),
]
