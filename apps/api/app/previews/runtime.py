import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.previews.models import PreviewLimits


@dataclass(frozen=True)
class SandboxJob:
    preview_id: str
    owner: str
    repository: str
    commit_sha: str
    routing_key: str
    runtime_profile: str
    limits: PreviewLimits


class PreviewRuntime(ABC):
    @abstractmethod
    def create_sandbox(self, job: SandboxJob) -> str: ...
    @abstractmethod
    def prepare_source(self, job: SandboxJob, sandbox_id: str) -> None: ...
    @abstractmethod
    def build(self, job: SandboxJob, sandbox_id: str) -> None: ...
    @abstractmethod
    def start(self, job: SandboxJob, sandbox_id: str) -> str: ...
    @abstractmethod
    def inspect(self, job: SandboxJob, sandbox_id: str) -> bool: ...
    @abstractmethod
    def terminate(self, sandbox_id: str) -> None: ...
    @abstractmethod
    def destroy(self, sandbox_id: str) -> None: ...
    @abstractmethod
    def get_logs(self, sandbox_id: str) -> str: ...


class LocalDockerRuntime(PreviewRuntime):
    """Development-only adapter. Never configure this provider in production."""

    IMAGE = (
        "nginxinc/nginx-unprivileged@sha256:"
        "65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0"
    )
    GIT_IMAGE = "alpine/git@sha256:062a01ad7a0eb17cff382bc5e26086b4d710e56dfdfdf001109a49b6d9bd378c"
    RELAY_IMAGE = (
        "alpine/socat@sha256:beb4a68d9e4fe6b0f21ea774a0fde6c31f580dde6368939ed70100c5385b015e"
    )
    NODE_IMAGE = "node@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32"
    PYTHON_IMAGE = "python@sha256:9c900dea9e8fb7e16277c179b555cc72d29a352dbc33cff48ad5a0412fd5bfc7"

    @staticmethod
    def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def create_sandbox(self, job: SandboxJob) -> str:
        volume = f"repolive-preview-{job.preview_id}"
        self._run(
            [
                "docker",
                "volume",
                "create",
                "--label",
                "repolive.preview=true",
                "--label",
                f"repolive.preview_id={job.preview_id}",
                volume,
            ]
        )
        self._run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--mount",
                f"type=volume,src={volume},dst=/work",
                "--entrypoint",
                "chown",
                self.GIT_IMAGE,
                "65532:65532",
                "/work",
            ]
        )
        return volume

    def prepare_source(self, job: SandboxJob, sandbox_id: str) -> None:
        repository_url = f"https://github.com/{job.owner}/{job.repository}.git"
        required_file = {
            "static_html_v1": "index.html",
            "python_flask_app_v1": "app.py",
            "python_fastapi_main_v1": "main.py",
            "python_django_manage_v1": "manage.py",
            "python_streamlit_app_v1": "app.py",
        }.get(job.runtime_profile, "package.json")
        script = (
            "git init /work && git -C /work config core.hooksPath /dev/null && "
            'git -C /work remote add origin "$1" && '
            'git -C /work fetch --depth=1 origin "$2" && '
            "git -C /work checkout --detach FETCH_HEAD && "
            'test "$(git -C /work rev-parse HEAD)" = "$2" && test -f "/work/$3"'
            ' && test -z "$(find /work -type l -print -quit)"'
            ' && test "$(find /work -type f | wc -l)" -le "$4"'
            ' && test "$(du -sk /work | cut -f1)" -le "$5"'
            " && rm -rf /work/.git"
        )
        self._run(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                f"repolive-fetch-{job.preview_id}",
                "--label",
                "repolive.preview=true",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--read-only",
                "--user",
                "65532:65532",
                "--env",
                "HOME=/tmp",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=8m",
                "--pids-limit",
                str(job.limits.pids),
                "--memory",
                f"{job.limits.memory_mb}m",
                "--cpus",
                str(job.limits.cpu_count),
                "--mount",
                f"type=volume,src={sandbox_id},dst=/work",
                "--entrypoint",
                "sh",
                self.GIT_IMAGE,
                "-c",
                script,
                "fetch",
                repository_url,
                job.commit_sha,
                required_file,
                str(job.limits.repository_files),
                str((job.limits.repository_bytes + 1023) // 1024),
            ],
            timeout=job.limits.build_timeout_seconds,
        )

    def build(self, job: SandboxJob, sandbox_id: str) -> None:
        if job.runtime_profile == "static_html_v1":
            return
        if job.runtime_profile.startswith("python_"):
            controlled_extra = (
                " uvicorn==0.35.0" if job.runtime_profile == "python_fastapi_main_v1" else ""
            )
            self._run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    f"repolive-build-{job.preview_id}",
                    "--label",
                    "repolive.preview=true",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges",
                    "--read-only",
                    "--user",
                    "65532:65532",
                    "--env",
                    "HOME=/tmp",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,size=512m",
                    "--pids-limit",
                    str(job.limits.pids),
                    "--memory",
                    f"{job.limits.memory_mb}m",
                    "--cpus",
                    str(job.limits.cpu_count),
                    "--mount",
                    f"type=volume,src={sandbox_id},dst=/work",
                    "--workdir",
                    "/work",
                    self.PYTHON_IMAGE,
                    "sh",
                    "-c",
                    "python -m venv .venv && .venv/bin/python -m pip install "
                    "--disable-pip-version-check --no-cache-dir --timeout 120 --retries 5 "
                    "-r requirements.txt" + controlled_extra,
                ],
                timeout=job.limits.build_timeout_seconds,
            )
            return
        if (
            job.runtime_profile.startswith("node_express_")
            or job.runtime_profile == "node_next_server_v1"
        ):
            trusted_build = (
                "./node_modules/.bin/next build"
                if job.runtime_profile == "node_next_server_v1"
                else "true"
            )
            self._run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    f"repolive-build-{job.preview_id}",
                    "--label",
                    "repolive.preview=true",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges",
                    "--read-only",
                    "--user",
                    "65532:65532",
                    "--env",
                    "HOME=/tmp",
                    "--env",
                    "NEXT_TELEMETRY_DISABLED=1",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,size=256m",
                    "--pids-limit",
                    str(job.limits.pids),
                    "--memory",
                    f"{job.limits.memory_mb}m",
                    "--cpus",
                    str(job.limits.cpu_count),
                    "--mount",
                    f"type=volume,src={sandbox_id},dst=/work",
                    "--workdir",
                    "/work",
                    "--entrypoint",
                    "sh",
                    self.NODE_IMAGE,
                    "-c",
                    "npm ci --ignore-scripts --no-audit --no-fund && " + trusted_build,
                ],
                timeout=job.limits.build_timeout_seconds,
            )
            return
        output = {
            "node_vite_v1": ("./node_modules/.bin/vite build", "dist"),
            "node_vite_tsc_v1": (
                "./node_modules/.bin/tsc && ./node_modules/.bin/vite build",
                "dist",
            ),
            "node_vite_tsc_noemit_v1": (
                "./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vite build",
                "dist",
            ),
            "node_cra_v1": ("./node_modules/.bin/react-scripts build", "build"),
        }.get(job.runtime_profile)
        if output is None:
            raise RuntimeError("Unsupported trusted runtime profile.")
        trusted_build, output_directory = output
        script = (
            "cd /work && npm ci --ignore-scripts --no-audit --no-fund && "
            + trusted_build
            + ' && test -f "$1/index.html" && '
            'mv "$1" .repolive-output && '
            "find . -mindepth 1 -maxdepth 1 ! -name .repolive-output -exec rm -rf -- {} + && "
            "mv .repolive-output/* . && rmdir .repolive-output"
        )
        self._run(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                f"repolive-build-{job.preview_id}",
                "--label",
                "repolive.preview=true",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--read-only",
                "--user",
                "65532:65532",
                "--env",
                "HOME=/tmp",
                "--env",
                "CI=true",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "--pids-limit",
                str(job.limits.pids),
                "--memory",
                f"{job.limits.memory_mb}m",
                "--cpus",
                str(job.limits.cpu_count),
                "--ulimit",
                "nofile=256:256",
                "--mount",
                f"type=volume,src={sandbox_id},dst=/work",
                "--entrypoint",
                "sh",
                self.NODE_IMAGE,
                "-c",
                script,
                "build",
                output_directory,
            ],
            timeout=job.limits.build_timeout_seconds,
        )

    def start(self, job: SandboxJob, sandbox_id: str) -> str:
        network = f"repolive-preview-{job.preview_id}"
        self._run(
            [
                "docker",
                "network",
                "create",
                "--internal",
                "--label",
                "repolive.preview=true",
                "--label",
                f"repolive.preview_id={job.preview_id}",
                network,
            ]
        )
        is_server_profile = (
            job.runtime_profile.startswith("python_")
            or job.runtime_profile.startswith("node_express_")
            or job.runtime_profile == "node_next_server_v1"
        )
        application_args = [
            "docker",
            "run",
            "-d",
            "--name",
            f"repolive-preview-{job.preview_id}",
            "--label",
            "repolive.preview=true",
            "--label",
            f"repolive.preview_id={job.preview_id}",
            "--read-only",
            "--network",
            network,
            "--user",
            "65532:65532" if is_server_profile else "101:101",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit",
            str(job.limits.pids),
            "--memory",
            f"{job.limits.memory_mb}m",
            "--cpus",
            str(job.limits.cpu_count),
            "--ulimit",
            "nofile=256:256",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=8m",
        ]
        python_commands = {
            "python_flask_app_v1": [
                "/work/.venv/bin/python",
                "-m",
                "flask",
                "--app",
                "app:app",
                "run",
                "--host",
                "0.0.0.0",
                "--port",
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
            "python_django_manage_v1": [
                "/work/.venv/bin/python",
                "manage.py",
                "runserver",
                "0.0.0.0:8080",
                "--noreload",
            ],
            "python_streamlit_app_v1": [
                "/work/.venv/bin/python",
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.address=0.0.0.0",
                "--server.port=8080",
                "--server.headless=true",
            ],
        }
        node_entry = {
            "node_express_server_v1": "server.js",
            "node_express_app_v1": "app.js",
            "node_express_index_v1": "index.js",
        }.get(job.runtime_profile)
        if job.runtime_profile in python_commands:
            application_args.extend(
                [
                    "--env",
                    "PORT=8080",
                    "--env",
                    "HOST=0.0.0.0",
                    "--env",
                    "PYTHONDONTWRITEBYTECODE=1",
                    "--mount",
                    f"type=volume,src={sandbox_id},dst=/work",
                    "--workdir",
                    "/work",
                    self.PYTHON_IMAGE,
                    *python_commands[job.runtime_profile],
                ]
            )
        elif node_entry or job.runtime_profile == "node_next_server_v1":
            node_command = (
                ["/work/node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "8080"]
                if job.runtime_profile == "node_next_server_v1"
                else ["node", node_entry or "server.js"]
            )
            application_args.extend(
                [
                    "--env",
                    "PORT=8080",
                    "--env",
                    "HOST=0.0.0.0",
                    "--env",
                    "NODE_ENV=production",
                    "--env",
                    "HOME=/tmp",
                    "--env",
                    "NEXT_TELEMETRY_DISABLED=1",
                    "--mount",
                    f"type=volume,src={sandbox_id},dst=/work",
                    "--workdir",
                    "/work",
                    self.NODE_IMAGE,
                    *node_command,
                ]
            )
        else:
            application_args.extend(
                [
                    "--mount",
                    f"type=volume,src={sandbox_id},dst=/usr/share/nginx/html,readonly",
                    self.IMAGE,
                ]
            )
        self._run(application_args)
        relay = f"repolive-route-{job.preview_id}"
        self._run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                relay,
                "--label",
                "repolive.preview=true",
                "--label",
                f"repolive.preview_id={job.preview_id}",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--read-only",
                "--user",
                "65532:65532",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=4m",
                "--pids-limit",
                "32",
                "--memory",
                "32m",
                "--cpus",
                "0.1",
                "--publish",
                "127.0.0.1:0:8081",
                self.RELAY_IMAGE,
                "TCP-LISTEN:8081,fork,reuseaddr",
                f"TCP:{network}:8080",
            ]
        )
        self._run(["docker", "network", "connect", network, relay])
        port = self._run(["docker", "port", relay, "8081/tcp"]).stdout.strip()
        prefix = "127.0.0.1:"
        if not port.startswith(prefix) or not port.removeprefix(prefix).isdigit():
            raise RuntimeError("Docker returned an invalid loopback preview port.")
        return f"http://{port}"

    def inspect(self, job: SandboxJob, sandbox_id: str) -> bool:
        result = self._run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Running}}",
                f"repolive-preview-{job.preview_id}",
            ]
        )
        if result.stdout.strip() != "true":
            return False
        server_profile = (
            job.runtime_profile.startswith("python_")
            or job.runtime_profile.startswith("node_express_")
            or job.runtime_profile == "node_next_server_v1"
        )
        if not server_profile:
            return True
        for _ in range(30):
            health_command = (
                [
                    "/work/.venv/bin/python",
                    "-c",
                    "import urllib.error,urllib.request; "
                    "\ntry: urllib.request.urlopen('http://127.0.0.1:8080/', timeout=2)"
                    "\nexcept urllib.error.HTTPError as exc: raise SystemExit(exc.code >= 500)",
                ]
                if job.runtime_profile.startswith("python_")
                else [
                    "node",
                    "-e",
                    "fetch('http://127.0.0.1:8080/').then(r=>{if(r.status>=500)"
                    "process.exit(1)}).catch(()=>process.exit(1))",
                ]
            )
            health = subprocess.run(
                ["docker", "exec", f"repolive-preview-{job.preview_id}", *health_command],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if health.returncode == 0:
                return True
            time.sleep(0.5)
        return False

    def terminate(self, sandbox_id: str) -> None:
        preview_id = sandbox_id.removeprefix("repolive-preview-")
        subprocess.run(
            ["docker", "stop", "--time", "2", f"repolive-preview-{preview_id}"],
            check=False,
            capture_output=True,
            text=True,
        )

    def destroy(self, sandbox_id: str) -> None:
        preview_id = sandbox_id.removeprefix("repolive-preview-")
        subprocess.run(
            ["docker", "rm", "-f", f"repolive-preview-{preview_id}"],
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["docker", "rm", "-f", f"repolive-route-{preview_id}"],
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["docker", "volume", "rm", sandbox_id], check=False, capture_output=True, text=True
        )
        subprocess.run(
            ["docker", "network", "rm", f"repolive-preview-{preview_id}"],
            check=False,
            capture_output=True,
            text=True,
        )

    def get_logs(self, sandbox_id: str) -> str:
        preview_id = sandbox_id.removeprefix("repolive-preview-")
        result = self._run(["docker", "logs", "--tail", "100", f"repolive-preview-{preview_id}"])
        return result.stdout + result.stderr
