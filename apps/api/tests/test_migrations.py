from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config


def test_migrations_upgrade_and_downgrade_schema(tmp_path: Path) -> None:
    database = tmp_path / "migration-test.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    try:
        config = Config("apps/api/alembic.ini")
        config.set_main_option("script_location", "apps/api/alembic")
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == {
            "alembic_version",
            "analyses",
            "analysis_user_links",
            "anonymous_usage",
            "authenticated_usage",
        }
        analysis_pk = inspector.get_pk_constraint("analyses")
        assert analysis_pk["constrained_columns"] == ["public_id"]
        unique_constraints = inspector.get_unique_constraints("analyses")
        assert any(
            constraint["name"] == "uq_analysis_identity_version"
            for constraint in unique_constraints
        )
        links_pk = inspector.get_pk_constraint("analysis_user_links")
        assert set(links_pk["constrained_columns"]) == {"user_id", "public_id"}
        foreign_keys = inspector.get_foreign_keys("analysis_user_links")
        assert foreign_keys[0]["options"].get("ondelete") == "CASCADE"
        indexes = inspector.get_indexes("analysis_user_links")
        assert any(index["name"] == "ix_user_history_saved" for index in indexes)
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()


def test_migrations_render_for_postgresql_without_a_live_connection() -> None:
    output = StringIO()
    config = Config("apps/api/alembic.ini")
    config.set_main_option("script_location", "apps/api/alembic")
    config.set_main_option(
        "sqlalchemy.url", "postgresql+psycopg://user:password@invalid.example/repolive"
    )
    with redirect_stdout(output):
        command.upgrade(config, "head", sql=True)
    rendered = output.getvalue()
    assert "CREATE TABLE analyses" in rendered
    assert "uq_analysis_identity_version" in rendered
    assert "CREATE TABLE analysis_user_links" in rendered
    assert "CREATE TABLE authenticated_usage" in rendered
