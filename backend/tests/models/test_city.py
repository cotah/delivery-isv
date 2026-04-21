from app.models.city import City
from app.utils.slug import make_city_slug, slugify


class TestSlugify:
    def test_simple_name(self) -> None:
        assert slugify("Tarumirim") == "tarumirim"

    def test_with_accents(self) -> None:
        assert slugify("São João del Rei") == "sao-joao-del-rei"

    def test_with_punctuation(self) -> None:
        assert slugify("Belo Horizonte!") == "belo-horizonte"

    def test_empty_string(self) -> None:
        assert slugify("") == ""

    def test_only_symbols(self) -> None:
        assert slugify("!@#$%") == ""


class TestMakeCitySlug:
    def test_format(self) -> None:
        assert make_city_slug("Tarumirim", "MG") == "tarumirim-mg"

    def test_with_accents(self) -> None:
        assert make_city_slug("São Paulo", "SP") == "sao-paulo-sp"

    def test_uppercase_state(self) -> None:
        # state pode vir em uppercase, resultado sempre lowercase
        assert make_city_slug("Itanhomi", "MG") == "itanhomi-mg"


class TestCityModel:
    def test_has_correct_tablename(self) -> None:
        assert City.__tablename__ == "cities"

    def test_has_required_columns(self) -> None:
        columns = {c.name for c in City.__table__.columns}
        expected = {"id", "name", "state", "slug", "is_active", "created_at", "updated_at"}
        assert expected.issubset(columns)

    def test_slug_is_unique(self) -> None:
        slug_col = City.__table__.columns["slug"]
        assert slug_col.unique is True

    def test_has_no_deleted_at(self) -> None:
        # ADR-008: cities usa is_active em vez de soft delete
        columns = {c.name for c in City.__table__.columns}
        assert "deleted_at" not in columns
