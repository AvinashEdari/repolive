import time
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.store import get_analysis_store
from app.previews.models import PreviewLimits, PreviewStatus
from app.previews.runtime import LocalDockerRuntime, SandboxJob
from app.previews.sanitization import sanitize_log
from app.previews.store import PreviewStore


def process_one() -> bool:
    settings = get_settings()
    if (
        not settings.preview_execution_enabled
        or settings.preview_runtime_provider != "local_docker"
    ):
        raise RuntimeError("The local preview worker is disabled or misconfigured.")
    store = PreviewStore(get_analysis_store())
    row = store.claim(settings.preview_worker_id)
    if row is None:
        return False
    preview_id = str(row["preview_id"])
    sandbox_id: str | None = None
    limits = PreviewLimits(
        cpu_count=settings.preview_cpu_count,
        memory_mb=settings.preview_memory_mb,
        pids=settings.preview_pids_limit,
        build_timeout_seconds=settings.preview_build_timeout_seconds,
        runtime_seconds=settings.preview_runtime_seconds,
        log_bytes=settings.preview_log_bytes,
    )
    job = SandboxJob(
        preview_id=preview_id,
        owner=str(row["owner"]),
        repository=str(row["repository_name"]),
        commit_sha=str(row["commit_sha"]),
        routing_key=str(row["routing_key"]),
        limits=limits,
    )
    runtime = LocalDockerRuntime()
    try:
        if not store.transition(
            preview_id,
            PreviewStatus.CLONING,
            "Retrieving the immutable source revision.",
            started_at=datetime.now(UTC),
        ):
            return True
        sandbox_id = runtime.create_sandbox(job)
        runtime.prepare_source(job, sandbox_id)
        store.transition(
            preview_id,
            PreviewStatus.BUILDING,
            "Static profile requires no repository build command.",
            sandbox_provider_id=sandbox_id,
        )
        runtime.build(job, sandbox_id)
        store.transition(
            preview_id, PreviewStatus.STARTING, "Starting the controlled static server."
        )
        runtime.start(job, sandbox_id)
        if not runtime.inspect(job, sandbox_id):
            raise RuntimeError("Sandbox health check failed.")
        now = datetime.now(UTC)
        store.transition(
            preview_id,
            PreviewStatus.READY,
            "Preview is healthy.",
            ready_at=now,
            expires_at=now + timedelta(seconds=settings.preview_runtime_seconds),
        )
    except TimeoutError:
        store.transition(
            preview_id,
            PreviewStatus.TIMED_OUT,
            "Preview work exceeded its time limit.",
            failure_category="timeout",
            safe_failure_message="The preview timed out.",
        )
        if sandbox_id:
            runtime.destroy(sandbox_id)
    except Exception as exc:
        safe = sanitize_log(str(exc), min(settings.preview_log_bytes, 1000))
        store.transition(
            preview_id,
            PreviewStatus.FAILED,
            "Preview setup failed safely.",
            failure_category="runtime",
            safe_failure_message=safe or "Preview setup failed.",
        )
        if sandbox_id:
            runtime.destroy(sandbox_id)
    return True


def main() -> None:
    while True:
        if not process_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
