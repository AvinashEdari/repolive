import os
import subprocess
import sys
from pathlib import Path


def test_api_startup_fails_closed_with_unsafe_production_configuration() -> None:
    api_root = Path(__file__).parents[1]
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "production",
            "DATABASE_URL": "sqlite:///unsafe-production.db",
            "WEB_ORIGIN": "http://localhost:3000",
            "ALLOWED_HOSTS": "*",
            "SUPABASE_URL": "http://localhost:54321",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app"],
        cwd=api_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode != 0
    assert "Production requires a PostgreSQL DATABASE_URL" in result.stderr
