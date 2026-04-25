from app.models.category import Category


class TestCategoryStructure:
    def test_has_correct_tablename(self) -> None:
        assert Category.__tablename__ == "categories"

    def test_has_required_columns_not_nullable(self) -> None:
        cols = Category.__table__.columns
        required = ("id", "name", "slug", "is_active", "created_at", "updated_at")
        for col_name in required:
            assert col_name in cols, f"missing required column: {col_name}"
            assert cols[col_name].nullable is False, f"{col_name} should be NOT NULL"

    def test_has_no_deleted_at(self) -> None:
        # ADR-013: categories é tabela lookup sem soft delete — is_active basta
        cols = Category.__table__.columns
        assert "deleted_at" not in cols

    def test_name_is_unique(self) -> None:
        assert Category.__table__.columns["name"].unique is True

    def test_slug_is_unique(self) -> None:
        assert Category.__table__.columns["slug"].unique is True

    def test_is_active_defaults_to_true(self) -> None:
        col = Category.__table__.columns["is_active"]
        # Python-side default (usado quando ORM cria sem passar is_active)
        assert col.default is not None, "is_active must have Python default"
        # DB-side server_default (usado em raw SQL INSERT / seeds)
        assert col.server_default is not None, "is_active must have server_default"

    def test_does_not_have_timestamps_mixin_collision(self) -> None:
        # TimestampMixin aplicado sem conflito — created_at e updated_at
        # presentes, NOT NULL, com server_default do Postgres
        cols = Category.__table__.columns
        for col_name in ("created_at", "updated_at"):
            assert col_name in cols
            col = cols[col_name]
            assert col.nullable is False
            assert col.server_default is not None


class TestCategoryBehavior:
    def test_repr_uses_slug(self) -> None:
        cat = Category(name="Pizzaria", slug="pizzaria")
        assert "pizzaria" in repr(cat)


class TestCategoryDisplayOrder:
    """Ordenação de categorias (HIGH debt #2, 2026-04-26).

    Migration popula display_order sequencial via ROW_NUMBER OVER (ORDER BY
    created_at) — admin reorganiza depois pelo painel.
    """

    def test_display_order_default_zero(self) -> None:
        col = Category.__table__.columns["display_order"]
        assert col.default is not None
        assert col.default.arg == 0
        assert col.server_default is not None
        assert "0" in str(col.server_default.arg)

    def test_display_order_is_not_nullable(self) -> None:
        assert Category.__table__.columns["display_order"].nullable is False

    def test_repr_includes_display_order(self) -> None:
        cat = Category(name="Pizzaria", slug="pizzaria", display_order=5)
        r = repr(cat)
        assert "pizzaria" in r
        assert "5" in r
