from pathlib import PurePosixPath

from app.analysis.base import Analyzer
from app.schemas.analysis import ImportantFileFinding, TechnologyCategory, TechnologyFinding
from app.schemas.repository import RepositorySnapshot

_IMPORTANT_NAMES = {
    "readme.md": "Primary documentation",
    "license": "License",
    "license.md": "License",
    "package.json": "Node package manifest",
    "pyproject.toml": "Python project manifest",
    "requirements.txt": "Python dependency manifest",
    "dockerfile": "Container build definition",
    "docker-compose.yml": "Multi-container definition",
    "docker-compose.yaml": "Multi-container definition",
    "compose.yml": "Multi-container definition",
    "compose.yaml": "Multi-container definition",
    "cargo.toml": "Rust package manifest",
    "go.mod": "Go module manifest",
    "pom.xml": "Maven project manifest",
    "build.gradle": "Gradle build definition",
    "makefile": "Build automation",
    ".env.example": "Environment variable template",
}

_TECHNOLOGY_MARKERS: dict[str, tuple[str, TechnologyCategory]] = {
    "next.config.js": ("Next.js", "framework"),
    "next.config.mjs": ("Next.js", "framework"),
    "next.config.ts": ("Next.js", "framework"),
    "vite.config.js": ("Vite", "build_tool"),
    "vite.config.ts": ("Vite", "build_tool"),
    "angular.json": ("Angular", "framework"),
    "svelte.config.js": ("Svelte", "framework"),
    "astro.config.mjs": ("Astro", "framework"),
    "nuxt.config.ts": ("Nuxt", "framework"),
    "dockerfile": ("Docker", "infrastructure"),
    "docker-compose.yml": ("Docker Compose", "infrastructure"),
    "docker-compose.yaml": ("Docker Compose", "infrastructure"),
    "pnpm-lock.yaml": ("pnpm", "package_manager"),
    "yarn.lock": ("Yarn", "package_manager"),
    "package-lock.json": ("npm", "package_manager"),
    "poetry.lock": ("Poetry", "package_manager"),
    "uv.lock": ("uv", "package_manager"),
    "cargo.toml": ("Cargo", "build_tool"),
    "go.mod": ("Go modules", "package_manager"),
    "pom.xml": ("Maven", "build_tool"),
    "build.gradle": ("Gradle", "build_tool"),
}


class ImportantFileAnalyzer(Analyzer[list[ImportantFileFinding]]):
    def analyze(self, snapshot: RepositorySnapshot) -> list[ImportantFileFinding]:
        findings = []
        for file in snapshot.files:
            name = PurePosixPath(file.path).name.lower()
            role = _IMPORTANT_NAMES.get(name)
            if role is None and (name == "readme" or name.startswith("readme.")):
                role = "Primary documentation"
            if role is None and (name == "license" or name.startswith("license.")):
                role = "License"
            if role:
                findings.append(ImportantFileFinding(path=file.path, role=role))
            elif file.path.startswith(".github/workflows/"):
                findings.append(
                    ImportantFileFinding(path=file.path, role="GitHub Actions workflow")
                )
        return sorted(findings, key=lambda finding: finding.path.lower())


class TechnologyAnalyzer(Analyzer[list[TechnologyFinding]]):
    def analyze(self, snapshot: RepositorySnapshot) -> list[TechnologyFinding]:
        markers: dict[tuple[str, TechnologyCategory], list[str]] = {}
        for file in snapshot.files:
            name = PurePosixPath(file.path).name.lower()
            marker = _TECHNOLOGY_MARKERS.get(name)
            if marker:
                markers.setdefault(marker, []).append(file.path)
        findings = [
            TechnologyFinding(
                name=name,
                category=category,
                confidence="high",
                evidence=sorted(paths),
            )
            for (name, category), paths in markers.items()
        ]
        return sorted(findings, key=lambda finding: (finding.category, finding.name))
