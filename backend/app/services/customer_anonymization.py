"""Service stub para anonimização de Customer (LGPD).

Implementação completa virá quando o endpoint de "deletar minha conta"
for implementado. Por ora, este stub documenta o contrato esperado
conforme ADR-004.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.customer import Customer


def anonymize_customer(customer: Customer) -> None:
    """Anonimiza PII de um Customer em conformidade com LGPD.

    Plano de anonimização (ADR-004):
    - name → "Cliente Removido"
    - phone → "+5500000000000" + sufixo random (manter UNIQUE)
    - email → None
    - cpf → None
    - birth_date → None
    - is_active → False
    - deleted_at → now()

    IMPORTANTE: mantém o id e os relacionamentos (orders, addresses)
    intactos. Histórico preservado, PII removida.

    TODO: implementação completa virá com o endpoint DELETE /api/v1/users/me.
    """
    raise NotImplementedError(
        "anonymize_customer stub — implementação virá junto com endpoint DELETE /users/me"
    )
