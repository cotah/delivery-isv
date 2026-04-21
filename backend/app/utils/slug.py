import re
import unicodedata


def slugify(text: str) -> str:
    """Converte texto em slug URL-friendly.

    Remove acentos, converte pra minúsculo, substitui espaços/pontuação
    por hifens, remove hifens duplos.

    Exemplos:
        slugify("Tarumirim") -> "tarumirim"
        slugify("São João del Rei") -> "sao-joao-del-rei"
        slugify("Belo Horizonte!") -> "belo-horizonte"
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    with_hyphens = re.sub(r"[^a-z0-9]+", "-", lowered)
    return with_hyphens.strip("-")


def make_city_slug(name: str, state: str) -> str:
    """Gera slug de cidade no formato 'nome-cidade-uf'.

    Exemplos:
        make_city_slug("Tarumirim", "MG") -> "tarumirim-mg"
        make_city_slug("São Paulo", "SP") -> "sao-paulo-sp"
    """
    return f"{slugify(name)}-{state.lower()}"
