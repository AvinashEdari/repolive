from collections import defaultdict
from pathlib import PurePosixPath

from app.analysis.base import Analyzer
from app.schemas.analysis import LanguageFinding
from app.schemas.repository import RepositorySnapshot

_LANGUAGES = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".java": "Java",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
    ".dart": "Dart",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".psm1": "PowerShell",
}
_IGNORED_PARTS = {"node_modules", "vendor", ".venv", "dist", "build", ".next"}


class LanguageAnalyzer(Analyzer[list[LanguageFinding]]):
    def analyze(self, snapshot: RepositorySnapshot) -> list[LanguageFinding]:
        counts: dict[str, int] = defaultdict(int)
        sizes: dict[str, int] = defaultdict(int)
        evidence: dict[str, list[str]] = defaultdict(list)
        for file in snapshot.files:
            path = PurePosixPath(file.path)
            if _IGNORED_PARTS.intersection(path.parts):
                continue
            language = _LANGUAGES.get(path.suffix.lower())
            if not language:
                continue
            counts[language] += 1
            sizes[language] += file.size_bytes or 0
            if len(evidence[language]) < 3:
                evidence[language].append(file.path)

        total_known_bytes = sum(sizes.values())
        total_files = sum(counts.values())
        findings = []
        for language in counts:
            numerator = sizes[language] if total_known_bytes else counts[language]
            denominator = total_known_bytes or total_files
            findings.append(
                LanguageFinding(
                    name=language,
                    file_count=counts[language],
                    known_bytes=sizes[language],
                    share_percent=round(100 * numerator / denominator, 1),
                    evidence=evidence[language],
                )
            )
        return sorted(findings, key=lambda finding: (-finding.share_percent, finding.name))
