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


class AddressType(StrEnum):
    """Tipo de endereço do customer (ADR-006, ADR-011)."""

    HOME = "home"
    WORK = "work"
    OTHER = "other"


class TaxIdType(StrEnum):
    """Tipo de documento fiscal (ADR-012)."""

    CPF = "cpf"
    CNPJ = "cnpj"


class StoreStatus(StrEnum):
    """Status operacional da Store (ADR-006).

    Fluxo típico:
    - pending: loja cadastrada, aguardando aprovação do admin
    - approved: loja aprovada e operando
    - rejected: admin rejeitou cadastro
    - blocked: admin suspendeu temporariamente (ex: reclamações)
    - paused: lojista pausou voluntariamente (ex: férias)
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    PAUSED = "paused"


class ProductStatus(StrEnum):
    """Status operacional do produto (ADR-006, ADR-014).

    Fluxo típico:
    - active: disponível pra compra
    - out_of_stock: esgotado temporariamente (lojista repõe depois)
    - paused: lojista pausou voluntariamente (indefinido)
    """

    ACTIVE = "active"
    OUT_OF_STOCK = "out_of_stock"
    PAUSED = "paused"


class AddonGroupType(StrEnum):
    """Tipo de seleção em um grupo de adicionais (ADR-014).

    - single: escolha única (ex: 'escolha a borda' — 1 borda só)
    - multiple: escolha múltipla (ex: 'escolha até 3 frutas')

    Limites quantitativos ficam em min_selections e max_selections
    no grupo, independente do tipo:
    - single: max_selections deve ser 1 (validado no modelo)
    - multiple: max_selections >= 1
    """

    SINGLE = "single"
    MULTIPLE = "multiple"


class OrderStatus(StrEnum):
    """Status do pedido (ADR-017).

    Máquina de estados:
        pending -> confirmed -> preparing -> out_for_delivery -> delivered (terminal)
        pending/confirmed/preparing -> canceled
        pending -> payment_failed (terminal)

    Transição out_for_delivery -> canceled NÃO permitida no piloto
    (ADR-017 refinamento R2). Sub-estados de cancelamento
    (by_customer/by_store) também não — motivo vai em
    OrderStatusLog.reason.

    Valores armazenados como VARCHAR(20) com CHECK dinâmico (ADR-006).
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELED = "canceled"
    PAYMENT_FAILED = "payment_failed"
