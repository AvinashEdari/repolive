from pathlib import PurePosixPath

from app.analysis.base import Analyzer
from app.schemas.analysis import ExplainableScore, QualitySignals, ScoreFactor
from app.schemas.repository import RepositorySnapshot


class QualityAnalyzer(Analyzer[QualitySignals]):
    def analyze(self, snapshot: RepositorySnapshot) -> QualitySignals:
        paths = [file.path.lower() for file in snapshot.files]
        names = {PurePosixPath(path).name for path in paths}
        return QualitySignals(
            has_readme=any(name == "readme" or name.startswith("readme.") for name in names),
            has_license=any(name == "license" or name.startswith("license.") for name in names),
            has_tests=any(
                part in {"test", "tests", "spec", "specs"}
                for path in paths
                for part in PurePosixPath(path).parts
            )
            or any(name.startswith(("test_", "test.")) for name in names),
            has_ci=any(path.startswith(".github/workflows/") for path in paths),
            has_container_config="dockerfile" in names
            or bool({"compose.yml", "compose.yaml", "docker-compose.yml"}.intersection(names)),
            has_environment_example=bool(
                {".env.example", ".env.sample", ".env.template"}.intersection(names)
            ),
        )


class ScoreAnalyzer:
    def analyze(self, quality: QualitySignals) -> list[ExplainableScore]:
        documentation = self._score(
            "Documentation",
            [
                (quality.has_readme, 55, "README present", "No README detected"),
                (quality.has_license, 20, "License present", "No license detected"),
                (
                    quality.has_environment_example,
                    25,
                    "Environment template present",
                    "No environment template detected",
                ),
            ],
        )
        engineering = self._score(
            "Engineering readiness",
            [
                (quality.has_tests, 40, "Tests detected", "No tests detected"),
                (quality.has_ci, 35, "CI workflow detected", "No CI workflow detected"),
                (
                    quality.has_container_config,
                    25,
                    "Container configuration detected",
                    "No container configuration detected",
                ),
            ],
        )
        return [documentation, engineering]

    @staticmethod
    def _score(
        name: str, factors: list[tuple[bool, int, str, str]]
    ) -> ExplainableScore:
        value = sum(weight for present, weight, _, _ in factors if present)
        explanations = [
            ScoreFactor(
                label=positive if present else negative,
                impact="positive" if present else "negative",
                evidence=[],
            )
            for present, _, positive, negative in factors
        ]
        return ExplainableScore(name=name, value=value, factors=explanations)
