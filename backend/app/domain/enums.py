"""Enums de domínio do ISV Delivery.

Todos conforme ADR-006: Python StrEnum usado diretamente como valor
no banco via VARCHAR + CHECK constraint.

Os enums específicos serão adicionados conforme os modelos forem
criados (OrderStatus, UserRole, PaymentMethod, DeliveryMode, etc.).
"""

from enum import StrEnum


class Environment(StrEnum):
    """Ambiente de execução. Espelha APP_ENV do Settings."""

    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"
