import re

PHONE_E164_REGEX = re.compile(r"^\+[1-9]\d{10,14}$")


def validate_phone_e164(phone: str) -> str:
    """Valida telefone em formato E.164.

    E.164: "+" seguido de código do país + número, 11 a 15 dígitos total.
    Exemplo válido: "+5531999887766"

    Levanta ValueError se inválido. Retorna o telefone (imutável)
    se válido, pra permitir uso em pipelines.
    """
    if not phone:
        raise ValueError("Phone is required")
    if not PHONE_E164_REGEX.match(phone):
        raise ValueError(f"Phone must be in E.164 format (e.g. +5531999887766), got: {phone!r}")
    return phone


def validate_cpf(cpf: str) -> str:
    """Valida CPF brasileiro.

    Aceita apenas 11 dígitos numéricos (sem máscara).
    Valida os dois dígitos verificadores conforme algoritmo oficial.

    Levanta ValueError se inválido. Retorna o CPF (imutável) se válido.
    """
    if not cpf:
        raise ValueError("CPF is required")
    if not cpf.isdigit() or len(cpf) != 11:
        raise ValueError(f"CPF must be 11 digits, got: {_mask_cpf(cpf)!r}")
    # Rejeita CPFs com todos dígitos iguais (111.111.111-11, etc.)
    if cpf == cpf[0] * 11:
        raise ValueError(f"CPF cannot have all identical digits: {_mask_cpf(cpf)!r}")

    # Primeiro dígito verificador
    sum_1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digit_1 = (sum_1 * 10) % 11
    if digit_1 == 10:
        digit_1 = 0
    if digit_1 != int(cpf[9]):
        raise ValueError(f"Invalid CPF check digit: {_mask_cpf(cpf)!r}")

    # Segundo dígito verificador
    sum_2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digit_2 = (sum_2 * 10) % 11
    if digit_2 == 10:
        digit_2 = 0
    if digit_2 != int(cpf[10]):
        raise ValueError(f"Invalid CPF check digit: {_mask_cpf(cpf)!r}")

    return cpf


def _mask_cpf(cpf: str) -> str:
    """Mascara CPF para logs: 111.***.***-35."""
    if len(cpf) != 11:
        return "***"
    return f"{cpf[:3]}.***.***-{cpf[-2:]}"


def mask_cpf_for_log(cpf: str | None) -> str:
    """Versão pública pra uso em logs. None-safe."""
    if cpf is None:
        return "<none>"
    return _mask_cpf(cpf)


def mask_phone_for_log(phone: str | None) -> str:
    """Mascara telefone E.164 pra logs: +55*********66."""
    if phone is None:
        return "<none>"
    if len(phone) < 6:
        return "***"
    return f"{phone[:3]}{'*' * (len(phone) - 5)}{phone[-2:]}"
