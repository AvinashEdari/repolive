import json
import re
from pathlib import PurePosixPath

from app.schemas.analysis import (
    CompatibilityFinding,
    InsightFinding,
    Platform,
    PrerequisiteFinding,
    QualitySignals,
    RuntimeFinding,
    SetupStep,
)
from app.schemas.repository import RepositorySnapshot

_ALL_PLATFORMS: list[Platform] = ["Windows", "Linux", "macOS"]
_ENV_NAME = re.compile(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
_SETUP_HEADING = re.compile(r"(?im)^#{1,3}\s+(?:installation|setup|getting started|quickstart)\s*$")
_NEXT_HEADING = re.compile(r"(?m)^#{1,3}\s+")
_CODE_FENCE = re.compile(r"```(?:bash|sh|shell|powershell|console)?\s*\n(.*?)```", re.DOTALL)


class GuidanceAnalyzer:
    def analyze(
        self,
        snapshot: RepositorySnapshot,
        runtimes: list[RuntimeFinding],
        quality: QualitySignals,
    ) -> tuple[
        list[SetupStep],
        list[PrerequisiteFinding],
        list[CompatibilityFinding],
        list[InsightFinding],
        list[InsightFinding],
        list[InsightFinding],
        list[InsightFinding],
    ]:
        steps = self._steps(snapshot)
        prerequisites = [
            PrerequisiteFinding(
                name=item.runtime,
                version_constraint=item.version_constraint,
                confidence="high" if item.version_constraint else "medium",
                evidence=item.evidence,
            )
            for item in runtimes
        ]
        environment_files = [
            file for file in snapshot.files if PurePosixPath(file.path).name == ".env.example"
        ]
        for file in environment_files:
            for name in _ENV_NAME.findall(file.text_content or ""):
                prerequisites.append(
                    PrerequisiteFinding(
                        name=f"Environment variable: {name}",
                        version_constraint=None,
                        confidence="high",
                        evidence=[file.path],
                    )
                )
        compatibility = self._compatibility(snapshot, runtimes)
        strengths, risks, missing = self._insights(snapshot, quality)
        unknowns = [
            InsightFinding(
                label="Exact CPU, memory, disk, and GPU requirements are not declared.",
                evidence=[],
            )
        ]
        if not runtimes:
            unknowns.append(
                InsightFinding(label="Runtime version requirements are not declared.", evidence=[])
            )
        unknowns.extend(
            InsightFinding(label=warning, evidence=[]) for warning in snapshot.ingestion_warnings
        )
        return steps, prerequisites, compatibility, strengths, risks, missing, unknowns

    def _steps(self, snapshot: RepositorySnapshot) -> list[SetupStep]:
        steps: list[SetupStep] = []
        paths = {file.path.lower() for file in snapshot.files}
        for file in snapshot.files:
            name = PurePosixPath(file.path).name.lower()
            if name.startswith("readme") and file.text_content:
                steps.extend(self._readme_steps(file.path, file.text_content))
            elif name == "package.json" and file.text_content:
                steps.extend(self._node_steps(file.path, file.text_content, paths))
            elif name == "requirements.txt":
                steps.append(
                    self._derived(
                        "Install Python dependencies",
                        f"python -m pip install -r {file.path}",
                        file.path,
                    )
                )
            elif name == "pyproject.toml":
                steps.append(
                    self._derived(
                        "Install the Python project", "python -m pip install .", file.path
                    )
                )
            elif name == "cargo.toml":
                steps.append(self._derived("Build the Rust project", "cargo build", file.path))
            elif name == "go.mod":
                steps.append(self._derived("Download Go modules", "go mod download", file.path))
            elif name == "pom.xml":
                command = "./mvnw package" if "mvnw" in paths else "mvn package"
                steps.append(self._derived("Build the Maven project", command, file.path))
            elif name in {"build.gradle", "build.gradle.kts"}:
                command = "./gradlew build" if "gradlew" in paths else "gradle build"
                steps.append(self._derived("Build the Gradle project", command, file.path))
            elif name == "gemfile":
                steps.append(self._derived("Install Ruby gems", "bundle install", file.path))
            elif name == "composer.json":
                steps.append(self._derived("Install PHP packages", "composer install", file.path))
            elif name.endswith((".csproj", ".fsproj", ".vbproj")):
                steps.append(self._derived("Restore .NET packages", "dotnet restore", file.path))
        if any(
            PurePosixPath(path).name.startswith(("compose.", "docker-compose.")) for path in paths
        ):
            steps.append(
                self._derived(
                    "Start declared containers",
                    "docker compose up",
                    "compose configuration",
                )
            )
        return self._dedupe_steps(steps)

    def _readme_steps(self, path: str, content: str) -> list[SetupStep]:
        """Extract bounded display-only commands from explicit README setup sections."""
        steps: list[SetupStep] = []
        for heading in list(_SETUP_HEADING.finditer(content))[:4]:
            section_start = heading.end()
            next_heading = _NEXT_HEADING.search(content, section_start)
            section = content[section_start : next_heading.start() if next_heading else None]
            for fence in list(_CODE_FENCE.finditer(section))[:3]:
                commands = [line.strip() for line in fence.group(1).splitlines()]
                commands = [
                    line.removeprefix("$ ")
                    for line in commands
                    if line and not line.startswith(("#", ">"))
                ][:8]
                for command in commands:
                    steps.append(
                        SetupStep(
                            title="Repository README instruction",
                            command=command[:500],
                            origin="repository",
                            source_path=path,
                            platforms=_ALL_PLATFORMS,
                        )
                    )
        return steps[:12]

    def _node_steps(self, path: str, content: str, paths: set[str]) -> list[SetupStep]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []
        manager = "npm"
        install = "npm install"
        if "pnpm-lock.yaml" in paths:
            manager, install = "pnpm", "pnpm install"
        elif "yarn.lock" in paths:
            manager, install = "yarn", "yarn install"
        steps = [self._derived(f"Install dependencies with {manager}", install, path)]
        scripts = payload.get("scripts", {})
        if isinstance(scripts, dict):
            for script_name in ("dev", "start", "build", "test"):
                command = scripts.get(script_name)
                if isinstance(command, str):
                    steps.append(
                        SetupStep(
                            title=f"Repository script: {script_name}",
                            command=command,
                            origin="repository",
                            source_path=path,
                            platforms=_ALL_PLATFORMS,
                        )
                    )
        return steps

    @staticmethod
    def _derived(title: str, command: str, source: str) -> SetupStep:
        return SetupStep(
            title=title,
            command=command,
            origin="derived",
            source_path=source,
            platforms=_ALL_PLATFORMS,
        )

    @staticmethod
    def _dedupe_steps(steps: list[SetupStep]) -> list[SetupStep]:
        unique = {(step.title, step.command, step.source_path): step for step in steps}
        return list(unique.values())

    @staticmethod
    def _compatibility(
        snapshot: RepositorySnapshot, runtimes: list[RuntimeFinding]
    ) -> list[CompatibilityFinding]:
        paths = {file.path.lower() for file in snapshot.files}
        findings = [
            CompatibilityFinding(
                subject="Operating system",
                status="unknown",
                detail="No machine profile was supplied; OS compatibility cannot be confirmed.",
                evidence=[],
            )
        ]
        if "dockerfile" in paths:
            findings.append(
                CompatibilityFinding(
                    subject="Container runtime",
                    status="conditional",
                    detail="Docker is required to use the declared container build.",
                    evidence=["Dockerfile"],
                )
            )
        for runtime in runtimes:
            findings.append(
                CompatibilityFinding(
                    subject=runtime.runtime,
                    status="conditional",
                    detail=(
                        f"Requires {runtime.runtime} {runtime.version_constraint}."
                        if runtime.version_constraint
                        else f"Requires {runtime.runtime}; no version is declared."
                    ),
                    evidence=runtime.evidence,
                )
            )
        return findings

    @staticmethod
    def _insights(
        snapshot: RepositorySnapshot, quality: QualitySignals
    ) -> tuple[list[InsightFinding], list[InsightFinding], list[InsightFinding]]:
        strengths: list[InsightFinding] = []
        risks: list[InsightFinding] = []
        missing: list[InsightFinding] = []
        checks = [
            (quality.has_readme, "README documentation", "README", "README.md"),
            (quality.has_license, "License declaration", "license", "LICENSE"),
            (quality.has_tests, "Automated tests", "tests", "tests/"),
            (quality.has_ci, "Continuous integration", "CI workflow", ".github/workflows/"),
        ]
        for present, positive, absent, evidence in checks:
            target = strengths if present else missing
            target.append(
                InsightFinding(
                    label=f"{positive} detected." if present else f"No {absent} detected.",
                    evidence=[evidence] if present else [],
                )
            )
        if snapshot.metadata.archived:
            risks.append(
                InsightFinding(label="GitHub marks this repository as archived.", evidence=[])
            )
        node_lockfiles = {
            PurePosixPath(file.path).name.lower()
            for file in snapshot.files
            if PurePosixPath(file.path).name.lower()
            in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
        }
        if len(node_lockfiles) > 1:
            risks.append(
                InsightFinding(
                    label="Multiple Node.js lockfiles may indicate conflicting package managers.",
                    evidence=sorted(node_lockfiles),
                )
            )
        if not quality.has_tests or not quality.has_ci:
            risks.append(
                InsightFinding(
                    label="Engineering changes may have limited automated verification.",
                    evidence=[],
                )
            )
        return strengths, risks, missing
