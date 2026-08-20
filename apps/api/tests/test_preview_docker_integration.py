import os
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

from app.analysis.pipeline import AnalysisPipeline
from app.core.config import Settings
from app.db.store import AnalysisStore
from app.previews import router as preview_router
from app.previews import worker as preview_worker
from app.previews.models import PreviewLimits, PreviewStatus
from app.previews.policy import PreviewPolicy
from app.previews.runtime import LocalDockerRuntime, SandboxJob
from app.previews.store import PreviewStore
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_PREVIEW_DOCKER_TESTS") != "1",
    reason="requires an explicitly approved local Docker engine",
)


def test_exact_commit_static_site_is_served_and_destroyed() -> None:
    preview_id = "integration_static_01"
    sandbox_id = f"repolive-preview-{preview_id}"
    job = SandboxJob(
        preview_id=preview_id,
        owner="mdn",
        repository="beginner-html-site-styled",
        commit_sha="6c7a360ddb4a0d75be06044bf8a914f260ff10c7",
        routing_key="integration-routing-key-0001",
        runtime_profile="static_html_v1",
        limits=PreviewLimits(
            cpu_count=0.5,
            memory_mb=128,
            pids=64,
            build_timeout_seconds=60,
            runtime_seconds=60,
            log_bytes=65536,
        ),
    )
    runtime = LocalDockerRuntime()
    try:
        assert runtime.create_sandbox(job) == sandbox_id
        runtime.prepare_source(job, sandbox_id)
        runtime.build(job, sandbox_id)
        endpoint = runtime.start(job, sandbox_id)
        assert endpoint.startswith("http://127.0.0.1:")
        assert runtime.inspect(job, sandbox_id)
        response = httpx.get(endpoint, timeout=10)
        assert response.status_code == 200
        assert "Mozilla is cool" in response.text
        inspect = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.Config.User}}|{{.HostConfig.ReadonlyRootfs}}|"
                "{{.HostConfig.Privileged}}|{{.HostConfig.PidsLimit}}|"
                "{{.HostConfig.SecurityOpt}}",
                f"repolive-preview-{preview_id}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        assert inspect.startswith("101:101|true|false|64|")
        assert "no-new-privileges" in inspect
        network = subprocess.run(
            [
                "docker",
                "network",
                "inspect",
                "--format",
                "{{.Internal}}",
                f"repolive-preview-{preview_id}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        assert network == "true"
        denied = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                f"repolive-preview-{preview_id}",
                "--user",
                "65532:65532",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--entrypoint",
                "sh",
                LocalDockerRuntime.GIT_IMAGE,
                "-c",
                "wget -T 2 -qO- http://169.254.169.254/ || wget -T 2 -qO- https://github.com/",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert denied.returncode != 0
        mounts = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .Mounts}}",
                f"repolive-preview-{preview_id}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        assert "docker.sock" not in mounts
        assert '"Type":"volume"' in mounts
    finally:
        runtime.terminate(sandbox_id)
        runtime.destroy(sandbox_id)
    remaining = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=repolive.preview_id={preview_id}",
            "--format",
            "{{.Names}}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    assert remaining == ""


def test_locked_vite_site_is_cloned_built_served_and_destroyed() -> None:
    preview_id = "integration_vite_01"
    sandbox_id = f"repolive-preview-{preview_id}"
    job = SandboxJob(
        preview_id=preview_id,
        owner="paultranvan",
        repository="solitaire",
        commit_sha="9ba4afadee11690bba375d4ea31e06855ce63f17",
        routing_key="integration-routing-key-vite-0001",
        runtime_profile="node_vite_tsc_noemit_v1",
        limits=PreviewLimits(
            cpu_count=1,
            memory_mb=512,
            pids=128,
            build_timeout_seconds=300,
            runtime_seconds=60,
            log_bytes=65536,
        ),
    )
    runtime = LocalDockerRuntime()
    try:
        assert runtime.create_sandbox(job) == sandbox_id
        runtime.prepare_source(job, sandbox_id)
        runtime.build(job, sandbox_id)
        endpoint = runtime.start(job, sandbox_id)
        response = httpx.get(endpoint, timeout=10)
        assert response.status_code == 200
        assert "Solitaire" in response.text
        assert runtime.inspect(job, sandbox_id)
    finally:
        runtime.terminate(sandbox_id)
        runtime.destroy(sandbox_id)


def test_root_flask_app_is_cloned_built_served_and_destroyed() -> None:
    preview_id = "integration_flask_01"
    sandbox_id = f"repolive-preview-{preview_id}"
    job = SandboxJob(
        preview_id=preview_id,
        owner="adyapathak22",
        repository="ipl-dashboard",
        commit_sha="0f75a217696d2220b830ae13dade6303149881f1",
        routing_key="integration-routing-key-flask-0001",
        runtime_profile="python_flask_app_v1",
        limits=PreviewLimits(
            cpu_count=1,
            memory_mb=1024,
            pids=128,
            build_timeout_seconds=600,
            runtime_seconds=60,
            log_bytes=65536,
        ),
    )
    runtime = LocalDockerRuntime()
    try:
        assert runtime.create_sandbox(job) == sandbox_id
        runtime.prepare_source(job, sandbox_id)
        runtime.build(job, sandbox_id)
        endpoint = runtime.start(job, sandbox_id)
        assert runtime.inspect(job, sandbox_id)
        response = httpx.get(endpoint, timeout=10)
        assert response.status_code == 200
        assert "IPL" in response.text
    finally:
        runtime.terminate(sandbox_id)
        runtime.destroy(sandbox_id)


def test_database_queue_worker_router_stop_and_cleanup(
    monkeypatch, request: pytest.FixtureRequest
) -> None:
    analysis_store = AnalysisStore("sqlite:///:memory:")
    report = AnalysisPipeline().analyze(
        RepositorySnapshot(
            repository=RepositoryReference(
                owner="mdn",
                name="beginner-html-site-styled",
                canonical_url="https://github.com/mdn/beginner-html-site-styled",
            ),
            metadata=RepositoryMetadata(
                description="Integration fixture",
                default_branch="main",
                commit_sha="6c7a360ddb4a0d75be06044bf8a914f260ff10c7",
                stars=0,
                forks=0,
                open_issues=0,
                size_kib=1,
                archived=False,
                license_spdx=None,
                primary_language="HTML",
                last_pushed_at=None,
            ),
            files=[RepositoryFile(path="index.html", size_bytes=100)],
        )
    )
    stored = analysis_store.save(
        report, "integration-anonymous-identifier", 5, user_id="integration-user"
    )
    assert stored.public_id
    settings = Settings(
        preview_execution_enabled=True,
        preview_runtime_provider="local_docker",
        preview_queue_provider="database",
        preview_router_base_url="http://preview.localhost:8081",
        preview_runtime_seconds=60,
    )
    policy = PreviewPolicy(settings).evaluate(stored)
    assert policy.detected_profile
    store = PreviewStore(analysis_store, settings.preview_router_base_url)
    preview = store.create(
        stored.public_id,
        "integration-user",
        policy.detected_profile,
        PreviewPolicy.VERSION,
        5,
        1,
    )
    request.addfinalizer(
        lambda: LocalDockerRuntime().destroy(f"repolive-preview-{preview.preview_id}")
    )
    store.transition(preview.preview_id, PreviewStatus.POLICY_CHECK, "policy approved")
    store.transition(preview.preview_id, PreviewStatus.QUEUED, "queued")
    monkeypatch.setattr(preview_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(preview_worker, "get_analysis_store", lambda: analysis_store)
    monkeypatch.setattr(preview_router, "get_settings", lambda: settings)
    monkeypatch.setattr(preview_router, "get_analysis_store", lambda: analysis_store)
    assert preview_worker.process_one()
    ready = store.get(preview.preview_id, "integration-user")
    assert ready.status == PreviewStatus.READY
    assert ready.preview_url
    response = TestClient(preview_router.app, base_url=ready.preview_url).get("/")
    assert response.status_code == 200
    assert "Mozilla is cool" in response.text
    assert store.transition(preview.preview_id, PreviewStatus.STOPPING, "stop requested")
    assert TestClient(preview_router.app, base_url=ready.preview_url).get("/").status_code == 404
    assert preview_worker.maintain() == 1
    destroyed = store.get(preview.preview_id, "integration-user")
    assert destroyed.status == PreviewStatus.DESTROYED
    assert destroyed.destroyed_at is not None
