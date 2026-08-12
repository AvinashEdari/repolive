import argparse
import json
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.store import AnalysisStore


def run_retention(days: int, execute: bool) -> dict[str, object]:
    if not 1 <= days <= 3650:
        raise ValueError("Retention days must be between 1 and 3650.")
    settings = get_settings()
    store = AnalysisStore(
        settings.database_url,
        create_schema=False,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
        connect_timeout=settings.database_connect_timeout_seconds,
    )
    cutoff = datetime.now(UTC) - timedelta(days=days)
    counts = store.apply_retention(cutoff) if execute else store.retention_candidates(cutoff)
    return {
        "mode": "execute" if execute else "dry-run",
        "cutoff": cutoff.isoformat(),
        "eligible": counts,
        "owned_analyses_preserved": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply RepoLive data-retention policy.")
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete eligible data. Without this flag, only report counts.",
    )
    args = parser.parse_args()
    print(json.dumps(run_retention(args.days, args.execute), sort_keys=True))


if __name__ == "__main__":
    main()
