import pytest

from app.utils.validators import (
    mask_cnpj_for_log,
    mask_cpf_for_log,
    mask_phone_for_log,
    mask_tax_id_for_log,
    validate_cnpj,
    validate_cpf,
    validate_phone_e164,
    validate_tax_id,
)


class TestValidatePhoneE164:
    # --- 4 válidos (multi-país) ---

    def test_valid_br_phone(self) -> None:
        assert validate_phone_e164("+5531999887766") == "+5531999887766"

    def test_valid_us_phone(self) -> None:
        assert validate_phone_e164("+15551234567") == "+15551234567"

    def test_valid_pt_phone(self) -> None:
        assert validate_phone_e164("+351912345678") == "+351912345678"

    def test_valid_ao_phone(self) -> None:
        # Angola — prova multi-país
        assert validate_phone_e164("+244923456789") == "+244923456789"

    # --- 7 inválidos ---

    def test_rejects_missing_plus(self) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            validate_phone_e164("5531999887766")

    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            validate_phone_e164("+55 31 99988-7766")

    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            validate_phone_e164("+5531999")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            validate_phone_e164("+5531999887766999")

    def test_rejects_letters(self) -> None:
        with pytest.raises(ValueError, match=r"E\.164 format"):
            validate_phone_e164("+5531abcde9876")

    def test_rejects_leading_zero_country_code(self) -> None:
        # E.164 não permite código de país começando em 0
        with pytest.raises(ValueError, match=r"E\.164 format"):
            validate_phone_e164("+031999887766")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="required"):
            validate_phone_e164("")


class TestValidateCpf:
    # --- 3 válidos (CPFs de teste conhecidos) ---

    def test_valid_cpf_1(self) -> None:
        assert validate_cpf("52998224725") == "52998224725"

    def test_valid_cpf_2(self) -> None:
        assert validate_cpf("11144477735") == "11144477735"

    def test_valid_cpf_3_zero_check_digit(self) -> None:
        # Cobre o branch `digit_1 == 10 -> digit_1 = 0` (primeiro DV = 0)
        assert validate_cpf("39053344705") == "39053344705"

    # --- 6 inválidos ---

    def test_rejects_cpf_with_mask(self) -> None:
        with pytest.raises(ValueError, match="11 digits"):
            validate_cpf("529.982.247-25")

    def test_rejects_cpf_10_digits(self) -> None:
        with pytest.raises(ValueError, match="11 digits"):
            validate_cpf("5299822472")

    def test_rejects_cpf_12_digits(self) -> None:
        with pytest.raises(ValueError, match="11 digits"):
            validate_cpf("529982247250")

    def test_rejects_cpf_all_same_digits(self) -> None:
        with pytest.raises(ValueError, match="identical"):
            validate_cpf("11111111111")

    def test_rejects_cpf_wrong_check_digit(self) -> None:
        # 52998224725 é válido; alterando o último dígito pra 0 quebra o DV
        with pytest.raises(ValueError, match="check digit"):
            validate_cpf("52998224720")

    def test_rejects_cpf_with_letters(self) -> None:
        with pytest.raises(ValueError, match="11 digits"):
            validate_cpf("5299822472a")

    def test_rejects_empty_cpf(self) -> None:
        with pytest.raises(ValueError, match="required"):
            validate_cpf("")


class TestMaskCpfForLog:
    def test_masks_valid_cpf(self) -> None:
        assert mask_cpf_for_log("52998224725") == "529.***.***-25"

    def test_returns_none_token_for_none(self) -> None:
        assert mask_cpf_for_log(None) == "<none>"

    def test_returns_stars_for_wrong_length(self) -> None:
        # String estranha / tamanho inválido — nunca expõe conteúdo
        assert mask_cpf_for_log("123") == "***"


class TestMaskPhoneForLog:
    def test_masks_valid_phone(self) -> None:
        result = mask_phone_for_log("+5531999887766")
        assert result == "+55*********66"
        # Preserva tamanho — dificulta fingerprinting reverso
        assert len(result) == len("+5531999887766")

    def test_returns_none_token_for_none(self) -> None:
        assert mask_phone_for_log(None) == "<none>"


class TestValidateCnpj:
    # --- 3 válidos (validados matematicamente pelo algoritmo oficial) ---

    def test_accepts_valid_cnpj_1(self) -> None:
        # "11222333000181" — DV calculado: 81 ✓
        assert validate_cnpj("11222333000181") == "11222333000181"

    def test_accepts_valid_cnpj_2(self) -> None:
        # "28989611000123" — DV calculado: 23 ✓
        # (substituído de "28989611000122" que o briefing pedia — DV correto é 23)
        assert validate_cnpj("28989611000123") == "28989611000123"

    def test_accepts_valid_cnpj_receita_federal(self) -> None:
        # "05570714000159" — CNPJ real da Receita Federal do Brasil
        assert validate_cnpj("05570714000159") == "05570714000159"

    # --- 7 inválidos ---

    def test_rejects_empty_cnpj(self) -> None:
        with pytest.raises(ValueError, match="required"):
            validate_cnpj("")

    def test_rejects_cnpj_13_digits(self) -> None:
        with pytest.raises(ValueError, match="14 digits"):
            validate_cnpj("1122233300018")

    def test_rejects_cnpj_15_digits(self) -> None:
        with pytest.raises(ValueError, match="14 digits"):
            validate_cnpj("112223330001811")

    def test_rejects_cnpj_with_letters(self) -> None:
        with pytest.raises(ValueError, match="14 digits"):
            validate_cnpj("1122233300018a")

    def test_rejects_cnpj_with_mask(self) -> None:
        with pytest.raises(ValueError, match="14 digits"):
            validate_cnpj("11.222.333/0001-81")

    def test_rejects_cnpj_all_identical_digits(self) -> None:
        with pytest.raises(ValueError, match="identical"):
            validate_cnpj("11111111111111")

    def test_rejects_cnpj_wrong_check_digit(self) -> None:
        # "28989611000122" — 14 dígitos, não-repetidos, mas segundo DV errado
        # (é exatamente o CNPJ que o briefing passou como "válido"
        # e que eu flaguei por ter DV errado)
        with pytest.raises(ValueError, match="check digit"):
            validate_cnpj("28989611000122")


class TestMaskCnpjForLog:
    def test_masks_valid_cnpj(self) -> None:
        # cnpj[:2]=11, cnpj[-3:-2]=1, cnpj[-2:]=81 → "11.***.***/***1-81"
        assert mask_cnpj_for_log("11222333000181") == "11.***.***/***1-81"

    def test_returns_none_token_for_none(self) -> None:
        assert mask_cnpj_for_log(None) == "<none>"

    def test_returns_stars_for_wrong_length(self) -> None:
        # String com tamanho inválido — nunca expõe conteúdo
        assert mask_cnpj_for_log("123") == "***"


class TestValidateTaxId:
    def test_validates_cpf_when_type_cpf(self) -> None:
        assert validate_tax_id("52998224725", "cpf") == "52998224725"

    def test_validates_cnpj_when_type_cnpj(self) -> None:
        assert validate_tax_id("11222333000181", "cnpj") == "11222333000181"

    def test_rejects_cpf_value_with_cnpj_type(self) -> None:
        # 11 dígitos de CPF com type='cnpj' — validate_cnpj exige 14 dígitos
        with pytest.raises(ValueError, match="14 digits"):
            validate_tax_id("52998224725", "cnpj")

    def test_rejects_cnpj_value_with_cpf_type(self) -> None:
        # 14 dígitos de CNPJ com type='cpf' — validate_cpf exige 11 dígitos
        with pytest.raises(ValueError, match="11 digits"):
            validate_tax_id("11222333000181", "cpf")

    def test_rejects_invalid_tax_id_type(self) -> None:
        with pytest.raises(ValueError, match="Invalid tax_id_type"):
            validate_tax_id("52998224725", "invalid")

    def test_rejects_empty_tax_id_type(self) -> None:
        with pytest.raises(ValueError, match="Invalid tax_id_type"):
            validate_tax_id("52998224725", "")


class TestMaskTaxIdForLog:
    def test_masks_as_cpf_when_type_cpf(self) -> None:
        assert mask_tax_id_for_log("52998224725", "cpf") == "529.***.***-25"

    def test_masks_as_cnpj_when_type_cnpj(self) -> None:
        assert mask_tax_id_for_log("11222333000181", "cnpj") == "11.***.***/***1-81"

    def test_infers_cpf_from_length_when_type_none(self) -> None:
        # 11 dígitos sem type declarado → infere CPF
        assert mask_tax_id_for_log("52998224725") == "529.***.***-25"

    def test_infers_cnpj_from_length_when_type_none(self) -> None:
        # 14 dígitos sem type declarado → infere CNPJ
        assert mask_tax_id_for_log("11222333000181") == "11.***.***/***1-81"

    def test_returns_none_placeholder_for_none(self) -> None:
        assert mask_tax_id_for_log(None) == "<none>"
