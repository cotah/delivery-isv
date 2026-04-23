"""Gerador de telefone E.164 brasileiro válido pra fixtures de teste.

User.phone é UNIQUE, então gerar novo a cada teste evita colisão.
Formato gerado: +55 + DDD (11-99) + 9 (celular) + 8 dígitos aleatórios =
13 dígitos após o "+" — bate a regex PHONE_E164_REGEX do validator.
"""

import random


def generate_valid_phone_e164() -> str:
    """Gera telefone E.164 brasileiro válido (+55<DDD><número>)."""
    area_code = random.randint(11, 99)
    subscriber = "9" + "".join(str(random.randint(0, 9)) for _ in range(8))
    return f"+55{area_code}{subscriber}"
