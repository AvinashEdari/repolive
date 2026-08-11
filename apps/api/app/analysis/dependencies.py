import json
import re
import tomllib

from app.analysis.base import Analyzer
from app.analysis.ecosystems import (
    ecosystem_runtime,
    parse_cargo,
    parse_composer,
    parse_dotnet,
    parse_gemfile,
    parse_go_mod,
    parse_gradle,
    parse_maven,
)
from app.schemas.analysis import (
    DependencyFinding,
    DependencyScope,
    RuntimeFinding,
    TechnologyFinding,
)
from app.schemas.repository import RepositoryFile, RepositorySnapshot

_REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)\s*([^;\s]+)?")


class DependencyAnalyzer(Analyzer[list[DependencyFinding]]):
    def analyze(self, snapshot: RepositorySnapshot) -> list[DependencyFinding]:
        findings: list[DependencyFinding] = []
        for file in snapshot.files:
            if file.text_content is None:
                continue
            name = file.path.rsplit("/", 1)[-1].lower()
            if name == "package.json":
                findings.extend(self._package_json(file))
            elif name == "requirements.txt":
                findings.extend(self._requirements(file))
            elif name == "pyproject.toml":
                findings.extend(self._pyproject(file))
            elif name == "cargo.toml":
                findings.extend(parse_cargo(file))
            elif name == "go.mod":
                findings.extend(parse_go_mod(file))
            elif name == "pom.xml":
                findings.extend(parse_maven(file))
            elif name in {"build.gradle", "build.gradle.kts"}:
                findings.extend(parse_gradle(file))
            elif name == "gemfile":
                findings.extend(parse_gemfile(file))
            elif name == "composer.json":
                findings.extend(parse_composer(file))
            elif name.endswith((".csproj", ".fsproj", ".vbproj")):
                findings.extend(parse_dotnet(file))
        unique = {
            (item.ecosystem, item.name.lower(), item.scope, item.source_path): item
            for item in findings
        }
        return sorted(
            unique.values(), key=lambda item: (item.ecosystem, item.name.lower(), item.scope)
        )

    @staticmethod
    def _package_json(file: RepositoryFile) -> list[DependencyFinding]:
        try:
            payload = json.loads(file.text_content or "")
        except json.JSONDecodeError:
            return []
        findings = []
        sections: dict[str, DependencyScope] = {
            "dependencies": "runtime",
            "devDependencies": "development",
            "optionalDependencies": "optional",
            "peerDependencies": "optional",
        }
        for section, scope in sections.items():
            dependencies = payload.get(section, {})
            if not isinstance(dependencies, dict):
                continue
            for name, constraint in dependencies.items():
                if isinstance(name, str) and isinstance(constraint, str):
                    findings.append(
                        DependencyFinding(
                            name=name,
                            version_constraint=constraint,
                            scope=scope,
                            ecosystem="npm",
                            source_path=file.path,
                        )
                    )
        return findings

    @staticmethod
    def _requirements(file: RepositoryFile) -> list[DependencyFinding]:
        findings = []
        for raw_line in (file.text_content or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            match = _REQUIREMENT.match(line)
            if match:
                findings.append(
                    DependencyFinding(
                        name=match.group(1),
                        version_constraint=match.group(2),
                        scope="runtime",
                        ecosystem="PyPI",
                        source_path=file.path,
                    )
                )
        return findings

    @staticmethod
    def _pyproject(file: RepositoryFile) -> list[DependencyFinding]:
        try:
            payload = tomllib.loads(file.text_content or "")
        except tomllib.TOMLDecodeError:
            return []
        project = payload.get("project", {})
        dependencies = project.get("dependencies", []) if isinstance(project, dict) else []
        findings = []
        for requirement in dependencies if isinstance(dependencies, list) else []:
            if not isinstance(requirement, str):
                continue
            match = _REQUIREMENT.match(requirement)
            if match:
                findings.append(
                    DependencyFinding(
                        name=match.group(1),
                        version_constraint=match.group(2),
                        scope="runtime",
                        ecosystem="PyPI",
                        source_path=file.path,
                    )
                )
        return findings


class RuntimeAnalyzer(Analyzer[list[RuntimeFinding]]):
    def analyze(self, snapshot: RepositorySnapshot) -> list[RuntimeFinding]:
        runtimes: dict[str, RuntimeFinding] = {}
        for file in snapshot.files:
            name = file.path.rsplit("/", 1)[-1].lower()
            if name == "package.json" and file.text_content:
                self._node_runtime(file, runtimes)
            elif name == "pyproject.toml" and file.text_content:
                self._python_runtime(file, runtimes)
            elif name == "go.mod" and file.text_content:
                match = re.search(r"(?m)^go\s+([0-9.]+)", file.text_content)
                runtimes["Go"] = RuntimeFinding(
                    runtime="Go",
                    version_constraint=match.group(1) if match else None,
                    evidence=[file.path],
                )
            else:
                runtime = ecosystem_runtime(file)
                if runtime:
                    runtimes[runtime.runtime] = runtime
        return sorted(runtimes.values(), key=lambda item: item.runtime)

    @staticmethod
    def _node_runtime(file: RepositoryFile, runtimes: dict[str, RuntimeFinding]) -> None:
        try:
            payload = json.loads(file.text_content or "")
        except json.JSONDecodeError:
            return
        engines = payload.get("engines", {})
        constraint = engines.get("node") if isinstance(engines, dict) else None
        runtimes["Node.js"] = RuntimeFinding(
            runtime="Node.js",
            version_constraint=constraint if isinstance(constraint, str) else None,
            evidence=[file.path],
        )

    @staticmethod
    def _python_runtime(file: RepositoryFile, runtimes: dict[str, RuntimeFinding]) -> None:
        try:
            payload = tomllib.loads(file.text_content or "")
        except tomllib.TOMLDecodeError:
            return
        project = payload.get("project", {})
        constraint = project.get("requires-python") if isinstance(project, dict) else None
        runtimes["Python"] = RuntimeFinding(
            runtime="Python",
            version_constraint=constraint if isinstance(constraint, str) else None,
            evidence=[file.path],
        )


class FrameworkDependencyAnalyzer:
    _FRAMEWORKS = {
        "react": "React",
        "next": "Next.js",
        "vue": "Vue",
        "nuxt": "Nuxt",
        "@angular/core": "Angular",
        "svelte": "Svelte",
        "astro": "Astro",
        "express": "Express",
        "@nestjs/core": "NestJS",
        "fastapi": "FastAPI",
        "flask": "Flask",
        "django": "Django",
        "rails": "Rails",
        "laravel/framework": "Laravel",
        "org.springframework.boot:spring-boot-starter": "Spring Boot",
        "microsoft.aspnetcore.app": "ASP.NET Core",
    }

    def analyze(self, dependencies: list[DependencyFinding]) -> list[TechnologyFinding]:
        evidence: dict[str, set[str]] = {}
        for dependency in dependencies:
            framework = self._FRAMEWORKS.get(dependency.name.lower())
            if framework:
                evidence.setdefault(framework, set()).add(dependency.source_path)
        return [
            TechnologyFinding(
                name=name,
                category="framework",
                confidence="high",
                evidence=sorted(paths),
            )
            for name, paths in sorted(evidence.items())
        ]
