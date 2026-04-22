"""Gerador de CNPJ válido pra fixtures de teste.

CNPJ é UNIQUE em Store, então gerar novo a cada teste evita colisão.
Usa o algoritmo oficial da Receita Federal — pesos conhecidos.
"""

import random


def generate_valid_cnpj() -> str:
    """Gera CNPJ válido (14 dígitos) pra fixtures de teste."""

    def _dv(digits: list[int], weights: list[int]) -> int:
        total = sum(d * w for d, w in zip(digits, weights, strict=True))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    base = [random.randint(0, 9) for _ in range(12)]

    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv1 = _dv(base, weights1)
    base.append(dv1)

    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv2 = _dv(base, weights2)
    base.append(dv2)

    return "".join(str(d) for d in base)
