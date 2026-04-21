import secrets
from uuid import UUID, uuid4


def new_uuid() -> UUID:
    """Gera um UUID v4 novo. Default para PKs do ISV (ADR-003)."""
    return uuid4()


def new_public_id(prefix: str = "ISV") -> str:
    """Gera um public_id curto no formato '<PREFIX>-<8 chars>'.

    Usado em orders, payments, refunds, support_tickets conforme ADR-003.
    Caracteres: letras A-Z (sem I/L/O) + dígitos 2-9 (sem 0/1) para evitar
    ambiguidade na leitura humana / por voz.

    Exemplo: 'ISV-A7K3X9P2'

    Colisão: alfabeto tem 31 caracteres, então 31^8 ≈ 852 bilhões de
    combinações. Verificação de unicidade fica a cargo do banco (coluna
    UNIQUE); em caso raro de colisão, retry no caller.
    """
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I/L
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{prefix}-{suffix}"
