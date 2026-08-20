import subprocess
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
    row = store.claim(
        settings.preview_worker_id, lease_seconds=settings.preview_build_timeout_seconds + 30
    )
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
        runtime_profile=str(row["runtime_profile"]),
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
        if not store.assign_sandbox(preview_id, settings.preview_worker_id, sandbox_id):
            runtime.destroy(sandbox_id)
            return True
        runtime.prepare_source(job, sandbox_id)
        if not store.transition(
            preview_id,
            PreviewStatus.BUILDING,
            "Running the trusted preview build profile.",
            heartbeat_at=datetime.now(UTC),
        ):
            runtime.destroy(sandbox_id)
            store.record_destroyed(
                preview_id, PreviewStatus.CANCELED, "Canceled sandbox storage was removed."
            )
            return True
        runtime.build(job, sandbox_id)
        if not store.transition(
            preview_id,
            PreviewStatus.STARTING,
            "Starting the controlled static output server.",
            heartbeat_at=datetime.now(UTC),
        ):
            runtime.destroy(sandbox_id)
            store.record_destroyed(
                preview_id, PreviewStatus.CANCELED, "Canceled sandbox storage was removed."
            )
            return True
        application_endpoint = runtime.start(job, sandbox_id)
        if not runtime.inspect(job, sandbox_id):
            raise RuntimeError("Sandbox health check failed.")
        now = datetime.now(UTC)
        if not store.transition(
            preview_id,
            PreviewStatus.READY,
            "Preview is healthy.",
            ready_at=now,
            expires_at=now + timedelta(seconds=settings.preview_runtime_seconds),
            application_endpoint=application_endpoint,
            lease_owner=None,
            lease_expires_at=None,
        ):
            runtime.destroy(sandbox_id)
            store.record_destroyed(
                preview_id, PreviewStatus.CANCELED, "Canceled sandbox storage was removed."
            )
    except (TimeoutError, subprocess.TimeoutExpired):
        transitioned = store.transition(
            preview_id,
            PreviewStatus.TIMED_OUT,
            "Preview work exceeded its time limit.",
            failure_category="timeout",
            safe_failure_message="The preview timed out.",
        )
        if sandbox_id:
            runtime.destroy(sandbox_id)
        if transitioned:
            store.record_destroyed(
                preview_id, PreviewStatus.TIMED_OUT, "Timed-out sandbox storage was removed."
            )
    except Exception as exc:
        safe = sanitize_log(str(exc), min(settings.preview_log_bytes, 1000))
        transitioned = store.transition(
            preview_id,
            PreviewStatus.FAILED,
            "Preview setup failed safely.",
            failure_category="runtime",
            safe_failure_message=safe or "Preview setup failed.",
        )
        if sandbox_id:
            runtime.destroy(sandbox_id)
        if transitioned:
            store.record_destroyed(
                preview_id, PreviewStatus.FAILED, "Failed sandbox storage was removed."
            )
    return True


def maintain() -> int:
    store = PreviewStore(get_analysis_store())
    runtime = LocalDockerRuntime()
    cleaned = 0
    for row in store.maintenance_candidates():
        preview_id = str(row["preview_id"])
        status = PreviewStatus(str(row["status"]))
        sandbox_id = row.get("sandbox_provider_id")
        if status == PreviewStatus.READY:
            if not store.transition(preview_id, PreviewStatus.EXPIRED, "Preview lifetime expired."):
                continue
            status = PreviewStatus.EXPIRED
        elif status in {PreviewStatus.CLONING, PreviewStatus.BUILDING, PreviewStatus.STARTING}:
            if not store.transition(
                preview_id,
                PreviewStatus.FAILED,
                "A stale worker lease was recovered.",
                failure_category="stale_lease",
                safe_failure_message="The preview worker stopped unexpectedly.",
            ):
                continue
            status = PreviewStatus.FAILED
        if isinstance(sandbox_id, str) and sandbox_id:
            runtime.terminate(sandbox_id)
            runtime.destroy(sandbox_id)
        if store.record_destroyed(preview_id, status, "Disposable sandbox storage was removed."):
            cleaned += 1
    return cleaned


def main() -> None:
    while True:
        maintain()
        if not process_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
