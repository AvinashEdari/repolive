from pathlib import Path

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config


def test_migrations_upgrade_and_downgrade_schema() -> None:
    database = Path("apps/api/tests/.migration-test.db").resolve()
    database.unlink(missing_ok=True)
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
            "anonymous_usage",
        }
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()
        database.unlink(missing_ok=True)
