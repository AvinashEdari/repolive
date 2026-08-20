import subprocess
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
    limits: PreviewLimits


class PreviewRuntime(ABC):
    @abstractmethod
    def create_sandbox(self, job: SandboxJob) -> str: ...
    @abstractmethod
    def prepare_source(self, job: SandboxJob, sandbox_id: str) -> None: ...
    @abstractmethod
    def build(self, job: SandboxJob, sandbox_id: str) -> None: ...
    @abstractmethod
    def start(self, job: SandboxJob, sandbox_id: str) -> None: ...
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

    IMAGE = "nginxinc/nginx-unprivileged:1.27-alpine"

    @staticmethod
    def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)

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
        return volume

    def prepare_source(self, job: SandboxJob, sandbox_id: str) -> None:
        repository_url = f"https://github.com/{job.owner}/{job.repository}.git"
        script = (
            "git init /work && git -C /work config core.hooksPath /dev/null && "
            'git -C /work remote add origin "$1" && '
            'git -C /work fetch --depth=1 origin "$2" && '
            "git -C /work checkout --detach FETCH_HEAD && "
            'test "$(git -C /work rev-parse HEAD)" = "$2" && test -f /work/index.html'
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
                "--pids-limit",
                str(job.limits.pids),
                "--memory",
                f"{job.limits.memory_mb}m",
                "--cpus",
                str(job.limits.cpu_count),
                "--mount",
                f"type=volume,src={sandbox_id},dst=/work",
                "alpine/git:2.47.2",
                "sh",
                "-c",
                script,
                "fetch",
                repository_url,
                job.commit_sha,
            ],
            timeout=job.limits.build_timeout_seconds,
        )

    def build(self, job: SandboxJob, sandbox_id: str) -> None:
        return None

    def start(self, job: SandboxJob, sandbox_id: str) -> None:
        self._run(
            [
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
                "none",
                "--user",
                "101:101",
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
                "--mount",
                f"type=volume,src={sandbox_id},dst=/usr/share/nginx/html,readonly",
                self.IMAGE,
            ]
        )

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
        return result.stdout.strip() == "true"

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
            ["docker", "volume", "rm", sandbox_id], check=False, capture_output=True, text=True
        )

    def get_logs(self, sandbox_id: str) -> str:
        preview_id = sandbox_id.removeprefix("repolive-preview-")
        return self._run(
            ["docker", "logs", "--tail", "100", f"repolive-preview-{preview_id}"]
        ).stdout
