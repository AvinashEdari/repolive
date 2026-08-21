import subprocess
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analysis.pipeline import AnalysisPipeline
from app.api.routes.previews import router as previews_api_router
from app.auth import AuthUser, require_user
from app.core.config import Settings, get_settings
from app.db.store import AnalysisStore, get_analysis_store
from app.previews import router as preview_router
from app.previews import worker as preview_worker
from app.previews.models import PreviewStatus
from app.previews.policy import PreviewPolicy
from app.previews.runtime import LocalDockerRuntime, SandboxJob
from app.previews.sanitization import sanitize_log
from app.previews.store import PreviewConflict, PreviewStore, preview_jobs
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)


def report(paths: list[str]):
    return AnalysisPipeline().analyze(
        RepositorySnapshot(
            repository=RepositoryReference(
                owner="example", name="site", canonical_url="https://github.com/example/site"
            ),
            metadata=RepositoryMetadata(
                description=None,
                default_branch="main",
                commit_sha="a" * 40,
                stars=0,
                forks=0,
                open_issues=0,
                size_kib=1,
                archived=False,
                license_spdx=None,
                primary_language="HTML",
                last_pushed_at=None,
            ),
            files=[RepositoryFile(path=path, size_bytes=10) for path in paths],
        )
    )


def node_report(package_json: str, lockfile: str = "package-lock.json"):
    snapshot = report(["package.json", lockfile, "src/main.jsx"]).snapshot
    snapshot.files[0].text_content = package_json
    return AnalysisPipeline().analyze(snapshot)


def flask_report():
    snapshot = report(["app.py", "requirements.txt", "templates/index.html"]).snapshot
    snapshot.files[1].text_content = "Flask>=2.3.0\n"
    return AnalysisPipeline().analyze(snapshot)


def python_server_report(entry: str, requirement: str):
    snapshot = report([entry, "requirements.txt"]).snapshot
    snapshot.files[1].text_content = f"{requirement}\n"
    return AnalysisPipeline().analyze(snapshot)


def test_static_policy_uses_only_trusted_profile() -> None:
    result = PreviewPolicy(Settings()).evaluate(report(["index.html", "styles.css"]))
    assert result.decision == "eligible"
    assert result.detected_profile == "static_html_v1"
    assert result.proposed_build_command == []


def test_policy_rejects_container_manifest_and_non_static_project() -> None:
    assert (
        PreviewPolicy(Settings()).evaluate(report(["index.html", "Dockerfile"])).decision
        == "ineligible"
    )
    assert PreviewPolicy(Settings()).evaluate(report(["src/main.py"])).decision == "ineligible"
    archived = PreviewPolicy(Settings()).evaluate(report(["README.md", "project.zip"]))
    assert "archive" in archived.reasons[0]
    assert any("entry point" in reason for reason in archived.reasons)


def test_policy_allows_only_locked_approved_node_frontend_builds() -> None:
    vite = PreviewPolicy(Settings()).evaluate(
        node_report('{"scripts":{"build":"vite build"},"devDependencies":{"vite":"^7.0.0"}}')
    )
    assert vite.decision == "eligible"
    assert vite.detected_profile == "node_vite_v1"
    assert vite.proposed_build_command == ["npm ci", "vite build"]
    vite_with_root_index = node_report(
        '{"scripts":{"build":"vite build"},"devDependencies":{"vite":"^7.0.0"}}'
    )
    vite_with_root_index.snapshot.files.append(RepositoryFile(path="index.html", size_bytes=10))
    assert (
        PreviewPolicy(Settings()).evaluate(vite_with_root_index).detected_profile == "node_vite_v1"
    )
    vite_typescript = PreviewPolicy(Settings()).evaluate(
        node_report(
            '{"scripts":{"build":"tsc && vite build"},'
            '"devDependencies":{"vite":"7","typescript":"5"}}'
        )
    )
    assert vite_typescript.detected_profile == "node_vite_tsc_v1"
    assert (
        PreviewPolicy(Settings())
        .evaluate(
            node_report(
                '{"scripts":{"build":"vite build && curl bad"},"devDependencies":{"vite":"7"}}'
            )
        )
        .decision
        == "ineligible"
    )


def test_policy_allows_fixed_root_flask_profile() -> None:
    result = PreviewPolicy(Settings()).evaluate(flask_report())
    assert result.decision == "eligible"
    assert result.detected_profile == "python_flask_app_v1"
    assert result.expected_application_port == 8080
    with_dockerfile = flask_report()
    with_dockerfile.snapshot.files.append(RepositoryFile(path="Dockerfile", size_bytes=10))
    assert PreviewPolicy(Settings()).evaluate(with_dockerfile).decision == "ineligible"


def test_policy_allows_controlled_web_server_profiles() -> None:
    next_result = PreviewPolicy(Settings()).evaluate(
        node_report(
            '{"scripts":{"build":"next build","start":"next start"},'
            '"dependencies":{"next":"16.0.0"}}'
        )
    )
    assert next_result.detected_profile == "node_next_server_v1"
    express_snapshot = node_report('{"dependencies":{"express":"5.0.0"}}')
    express_snapshot.snapshot.files.append(RepositoryFile(path="server.js", size_bytes=10))
    assert PreviewPolicy(Settings()).evaluate(express_snapshot).detected_profile == (
        "node_express_server_v1"
    )
    assert (
        PreviewPolicy(Settings())
        .evaluate(python_server_report("main.py", "fastapi>=0.100"))
        .detected_profile
        == "python_fastapi_main_v1"
    )
    assert (
        PreviewPolicy(Settings())
        .evaluate(python_server_report("manage.py", "Django>=5"))
        .detected_profile
        == "python_django_manage_v1"
    )
    assert (
        PreviewPolicy(Settings())
        .evaluate(python_server_report("app.py", "streamlit>=1.40"))
        .detected_profile
        == "python_streamlit_app_v1"
    )
    assert (
        PreviewPolicy(Settings())
        .evaluate(
            node_report(
                '{"scripts":{"build":"vite build"},"devDependencies":{"vite":"7"}}',
                "yarn.lock",
            )
        )
        .decision
        == "ineligible"
    )


def test_logs_strip_control_sequences_redact_and_truncate() -> None:
    value = sanitize_log("\x1b[31mtoken=abc\x00 https://user:pass@example.com " + "x" * 200, 80)
    assert "abc" not in value and "user:pass" not in value and "\x1b" not in value
    assert value.endswith("[TRUNCATED]")


def test_preview_store_enforces_ownership_concurrency_and_transitions() -> None:
    analysis_store = AnalysisStore("sqlite:///:memory:")
    saved = analysis_store.save(
        report(["index.html"]), "anonymous-identifier-long-enough", 5, user_id="user-1"
    )
    assert saved.public_id
    previews = PreviewStore(analysis_store)
    created = previews.create(saved.public_id, "user-1", "static_html_v1", "static-v1", 5, 1)
    assert created.commit_sha == "a" * 40
    assert previews.transition(created.preview_id, PreviewStatus.POLICY_CHECK, "checked")
    assert not previews.transition(created.preview_id, PreviewStatus.READY, "invalid")
    try:
        previews.create(saved.public_id, "user-1", "static_html_v1", "static-v1", 5, 1)
    except PreviewConflict:
        pass
    else:
        raise AssertionError("Concurrent limit must be transactional.")
    try:
        previews.get(created.preview_id, "user-2")
    except KeyError:
        pass
    else:
        raise AssertionError("Ownership must be enforced.")


def test_ready_route_is_opaque_and_removed_on_expiration() -> None:
    analysis_store = AnalysisStore("sqlite:///:memory:")
    saved = analysis_store.save(
        report(["index.html"]), "anonymous-identifier-long-enough", 5, user_id="user-1"
    )
    assert saved.public_id
    previews = PreviewStore(analysis_store)
    created = previews.create(saved.public_id, "user-1", "static_html_v1", "static-v1", 5, 1)
    previews.transition(created.preview_id, PreviewStatus.POLICY_CHECK, "checked")
    previews.transition(created.preview_id, PreviewStatus.QUEUED, "queued")
    previews.transition(created.preview_id, PreviewStatus.CLONING, "cloning")
    previews.transition(created.preview_id, PreviewStatus.BUILDING, "building")
    previews.transition(created.preview_id, PreviewStatus.STARTING, "starting")
    previews.transition(
        created.preview_id,
        PreviewStatus.READY,
        "ready",
        application_endpoint="http://127.0.0.1:49152",
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    with analysis_store.engine.connect() as connection:
        key = connection.execute(
            select(preview_jobs.c.routing_key).where(
                preview_jobs.c.preview_id == created.preview_id
            )
        ).scalar_one()
    assert previews.route(str(key)) == "http://127.0.0.1:49152"
    previews.transition(created.preview_id, PreviewStatus.STOPPING, "stop")
    assert previews.route(str(key)) is None
    assert previews.record_destroyed(created.preview_id, PreviewStatus.STOPPING, "removed")
    assert previews.get(created.preview_id, "user-1").status == PreviewStatus.DESTROYED


def test_local_runtime_uses_internal_network_and_loopback_publish(monkeypatch) -> None:
    calls: list[list[str]] = []

    def run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        output = "127.0.0.1:49152\n" if args[1:2] == ["port"] else ""
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(LocalDockerRuntime, "_run", staticmethod(run))
    runtime = LocalDockerRuntime()
    job = SandboxJob(
        preview_id="safe_preview_id",
        owner="owner",
        repository="repository",
        commit_sha="a" * 40,
        routing_key="opaque-routing-key-value",
        runtime_profile="static_html_v1",
        limits=PreviewPolicy(Settings()).evaluate(report(["index.html"])).limits,
    )
    assert runtime.start(job, "repolive-preview-safe_preview_id") == "http://127.0.0.1:49152"
    network_call, run_call, relay_call, connect_call, _ = calls
    assert "--internal" in network_call
    assert "--publish" not in run_call
    assert "--cap-drop=ALL" in run_call
    assert "--security-opt=no-new-privileges" in run_call
    assert ["--publish", "127.0.0.1:0:8081"] == relay_call[
        relay_call.index("--publish") : relay_call.index("--publish") + 2
    ]
    assert connect_call[1:3] == ["network", "connect"]


def test_local_runtime_uses_fixed_commands_for_server_profiles(monkeypatch) -> None:
    calls: list[list[str]] = []

    def run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        output = "127.0.0.1:49152\n" if args[1:2] == ["port"] else ""
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(LocalDockerRuntime, "_run", staticmethod(run))
    limits = PreviewPolicy(Settings()).evaluate(report(["index.html"])).limits
    expected_commands = {
        "node_express_server_v1": ["node", "server.js"],
        "node_next_server_v1": [
            "/work/node_modules/.bin/next",
            "start",
            "-H",
            "0.0.0.0",
            "-p",
            "8080",
        ],
        "python_fastapi_main_v1": [
            "/work/.venv/bin/python",
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
        ],
    }
    for profile, command in expected_commands.items():
        calls.clear()
        job = SandboxJob(
            preview_id="server_profile_id",
            owner="owner",
            repository="repository",
            commit_sha="a" * 40,
            routing_key="opaque-routing-key-value",
            runtime_profile=profile,
            limits=limits,
        )
        LocalDockerRuntime().start(job, "repolive-preview-server_profile_id")
        run_call = calls[1]
        assert run_call[-len(command) :] == command
        assert "PORT=8080" in run_call
        assert "--read-only" in run_call


def test_router_requires_opaque_preview_host_and_caps_headers(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def request(self, method: str, target: str) -> httpx.Response:
            assert method == "GET"
            assert target == "http://127.0.0.1:49152/assets/site.css"
            return httpx.Response(
                200,
                content=b"body{}",
                headers={"Content-Type": "text/css", "Set-Cookie": "unsafe=yes"},
            )

    monkeypatch.setattr(
        preview_router,
        "get_settings",
        lambda: Settings(preview_router_base_url="http://preview.localhost:8081"),
    )
    monkeypatch.setattr(
        preview_router.PreviewStore,
        "route",
        lambda self, key: "http://127.0.0.1:49152" if key == "opaque-routing-key-value" else None,
    )
    monkeypatch.setattr(preview_router.httpx, "Client", FakeClient)
    client = TestClient(
        preview_router.app, base_url="http://opaque-routing-key-value.preview.localhost:8081"
    )
    response = client.get("/assets/site.css")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/css"
    assert "set-cookie" not in response.headers
    assert (
        TestClient(preview_router.app, base_url="http://preview.localhost:8081")
        .get("/")
        .status_code
        == 404
    )


def test_preview_api_requires_owned_analysis_and_queues_exact_commit() -> None:
    analysis_store = AnalysisStore("sqlite:///:memory:")
    saved = analysis_store.save(
        report(["index.html"]), "api-anonymous-identifier-long", 5, user_id="owner-user"
    )
    assert saved.public_id
    settings = Settings(
        preview_execution_enabled=True,
        preview_runtime_provider="local_docker",
        preview_queue_provider="database",
        preview_router_base_url="http://preview.localhost:8081",
    )
    api = FastAPI()
    api.include_router(previews_api_router, prefix="/api/v1")
    api.dependency_overrides[get_analysis_store] = lambda: analysis_store
    api.dependency_overrides[get_settings] = lambda: settings
    api.dependency_overrides[require_user] = lambda: AuthUser("owner-user")
    client = TestClient(api)
    response = client.post(f"/api/v1/analyses/{saved.public_id}/previews")
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["commit_sha"] == "a" * 40
    api.dependency_overrides[require_user] = lambda: AuthUser("different-user")
    assert client.get(f"/api/v1/previews/{payload['preview_id']}").status_code == 404


def test_expiration_removes_route_and_destroys_sandbox(monkeypatch) -> None:
    analysis_store = AnalysisStore("sqlite:///:memory:")
    saved = analysis_store.save(
        report(["index.html"]), "expiry-anonymous-identifier", 5, user_id="user-1"
    )
    assert saved.public_id
    store = PreviewStore(analysis_store, "http://preview.localhost:8081")
    preview = store.create(saved.public_id, "user-1", "static_html_v1", "static-v1", 5, 1)
    for status in [
        PreviewStatus.POLICY_CHECK,
        PreviewStatus.QUEUED,
        PreviewStatus.CLONING,
        PreviewStatus.BUILDING,
        PreviewStatus.STARTING,
    ]:
        assert store.transition(preview.preview_id, status, status.value)
    assert store.transition(
        preview.preview_id,
        PreviewStatus.READY,
        "ready",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        sandbox_provider_id=f"repolive-preview-{preview.preview_id}",
        application_endpoint="http://127.0.0.1:49152",
    )
    destroyed: list[str] = []

    class FakeRuntime:
        def terminate(self, sandbox_id: str) -> None:
            destroyed.append(f"stop:{sandbox_id}")

        def destroy(self, sandbox_id: str) -> None:
            destroyed.append(f"destroy:{sandbox_id}")

    monkeypatch.setattr(preview_worker, "get_analysis_store", lambda: analysis_store)
    monkeypatch.setattr(preview_worker, "LocalDockerRuntime", FakeRuntime)
    assert preview_worker.maintain() == 1
    expired = store.get(preview.preview_id, "user-1")
    assert expired.status == PreviewStatus.EXPIRED
    assert expired.preview_url is None
    assert expired.destroyed_at is not None
    assert destroyed == [
        f"stop:repolive-preview-{preview.preview_id}",
        f"destroy:repolive-preview-{preview.preview_id}",
    ]
