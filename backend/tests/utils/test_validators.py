import pytest

from app.utils.validators import (
    mask_cpf_for_log,
    mask_phone_for_log,
    validate_cpf,
    validate_phone_e164,
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
