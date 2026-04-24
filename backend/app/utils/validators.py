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


def mask_phone_for_display(phone: str) -> str:
    """Mascara telefone E.164 preservando DDD + 4 últimos dígitos (UX).

    Formato: "+55 DD X*****ABCD"
    Exemplo: "+5531999887766" -> "+55 31 9*****7766"

    Usado em respostas de API onde cliente precisa reconhecer o número
    (confirmação de envio de OTP, dashboard de perfil). Menos privativo
    que mask_phone_for_log (que esconde DDD).

    Pressupõe phone já validado E.164 (usar validate_phone_e164 antes).

    Args:
        phone: telefone E.164 já validado, 13 chars (formato BR: "+55DDNNNNNNNNN")

    Returns:
        String mascarada legível para UX.

    Raises:
        ValueError: se phone for menor que 13 chars (formato inválido BR).
    """
    if not phone or len(phone) < 13:
        raise ValueError(f"Invalid phone for display mask: {phone!r}")

    country = phone[:3]
    ddd = phone[3:5]
    first = phone[5]
    last_four = phone[-4:]
    # Mascara o miolo do subscriber — entre first (pos 5) e last_four (pos -4).
    # BR celular moderno (14 chars, subscriber 9 dígitos) → 5 asteriscos.
    masked_middle = "*" * (len(phone) - 9)

    return f"{country} {ddd} {first}{masked_middle}{last_four}"


def validate_cnpj(cnpj: str) -> str:
    """Valida CNPJ brasileiro.

    Aceita apenas 14 dígitos numéricos (sem máscara).
    Valida os dois dígitos verificadores conforme algoritmo oficial
    da Receita Federal.

    Levanta ValueError se inválido. Retorna o CNPJ (imutável) se válido.
    """
    if not cnpj:
        raise ValueError("CNPJ is required")
    if not cnpj.isdigit() or len(cnpj) != 14:
        raise ValueError(f"CNPJ must be 14 digits, got: {_mask_cnpj(cnpj)!r}")
    # Rejeita CNPJs com todos dígitos iguais (11.111.111/1111-11, etc.)
    if cnpj == cnpj[0] * 14:
        raise ValueError(f"CNPJ cannot have all identical digits: {_mask_cnpj(cnpj)!r}")

    # Primeiro dígito verificador — multiplicadores 5,4,3,2,9,8,7,6,5,4,3,2
    weights_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_1 = sum(int(cnpj[i]) * weights_1[i] for i in range(12))
    digit_1 = sum_1 % 11
    digit_1 = 0 if digit_1 < 2 else 11 - digit_1
    if digit_1 != int(cnpj[12]):
        raise ValueError(f"Invalid CNPJ check digit: {_mask_cnpj(cnpj)!r}")

    # Segundo dígito verificador — multiplicadores 6,5,4,3,2,9,8,7,6,5,4,3,2
    weights_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_2 = sum(int(cnpj[i]) * weights_2[i] for i in range(13))
    digit_2 = sum_2 % 11
    digit_2 = 0 if digit_2 < 2 else 11 - digit_2
    if digit_2 != int(cnpj[13]):
        raise ValueError(f"Invalid CNPJ check digit: {_mask_cnpj(cnpj)!r}")

    return cnpj


def _mask_cnpj(cnpj: str) -> str:
    """Mascara CNPJ para logs: 12.***.***/***1-91."""
    if len(cnpj) != 14:
        return "***"
    return f"{cnpj[:2]}.***.***/***{cnpj[-3:-2]}-{cnpj[-2:]}"


def mask_cnpj_for_log(cnpj: str | None) -> str:
    """Versão pública pra uso em logs. None-safe."""
    if cnpj is None:
        return "<none>"
    return _mask_cnpj(cnpj)


def validate_tax_id(tax_id: str, tax_id_type: str) -> str:
    """Valida documento fiscal conforme o tipo declarado (ADR-012).

    Função canônica que orquestra a validação cruzada:
    - tax_id_type='cpf' → chama validate_cpf (11 dígitos)
    - tax_id_type='cnpj' → chama validate_cnpj (14 dígitos)
    - tax_id_type inválido → ValueError

    Chamada tanto pelo Pydantic (borda da API) quanto pelo SQLAlchemy
    (@validates no modelo Store), aplicando ADR-010 defense-in-depth.

    Retorna o tax_id (imutável) se válido.
    """
    if tax_id_type == "cpf":
        return validate_cpf(tax_id)
    if tax_id_type == "cnpj":
        return validate_cnpj(tax_id)
    raise ValueError(f"Invalid tax_id_type: {tax_id_type!r}. Expected 'cpf' or 'cnpj'.")


def mask_tax_id_for_log(tax_id: str | None, tax_id_type: str | None = None) -> str:
    """Mascara tax_id pra logs, escolhendo máscara conforme tipo.

    Se tax_id_type vier vazio, infere pelo tamanho (11 dígitos=CPF, 14=CNPJ).
    None-safe.
    """
    if tax_id is None:
        return "<none>"
    if tax_id_type == "cpf" or (tax_id_type is None and len(tax_id) == 11):
        return mask_cpf_for_log(tax_id)
    if tax_id_type == "cnpj" or (tax_id_type is None and len(tax_id) == 14):
        return mask_cnpj_for_log(tax_id)
    return "***"
