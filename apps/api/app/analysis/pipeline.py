from app.analysis.dependencies import (
    DependencyAnalyzer,
    FrameworkDependencyAnalyzer,
    RuntimeAnalyzer,
)
from app.analysis.guidance import GuidanceAnalyzer
from app.analysis.languages import LanguageAnalyzer
from app.analysis.quality import QualityAnalyzer, ScoreAnalyzer
from app.analysis.structure import ImportantFileAnalyzer, TechnologyAnalyzer
from app.schemas.analysis import AnalysisReport, DeterministicAnalysis, TechnologyFinding
from app.schemas.repository import RepositorySnapshot


class AnalysisPipeline:
    def __init__(self) -> None:
        self.language_analyzer = LanguageAnalyzer()
        self.technology_analyzer = TechnologyAnalyzer()
        self.important_file_analyzer = ImportantFileAnalyzer()
        self.dependency_analyzer = DependencyAnalyzer()
        self.runtime_analyzer = RuntimeAnalyzer()
        self.framework_dependency_analyzer = FrameworkDependencyAnalyzer()
        self.quality_analyzer = QualityAnalyzer()
        self.score_analyzer = ScoreAnalyzer()
        self.guidance_analyzer = GuidanceAnalyzer()

    def analyze(self, snapshot: RepositorySnapshot) -> AnalysisReport:
        dependencies = self.dependency_analyzer.analyze(snapshot)
        technologies = self._merge_technologies(
            self.technology_analyzer.analyze(snapshot),
            self.framework_dependency_analyzer.analyze(dependencies),
        )
        quality = self.quality_analyzer.analyze(snapshot)
        runtimes = self.runtime_analyzer.analyze(snapshot)
        (
            setup_steps,
            prerequisites,
            compatibility,
            strengths,
            risks,
            missing_essentials,
            unknowns,
        ) = self.guidance_analyzer.analyze(snapshot, runtimes, quality)
        project_types = self._project_types(snapshot, {item.name for item in technologies})
        return AnalysisReport(
            snapshot=snapshot,
            analysis=DeterministicAnalysis(
                purpose_summary=(
                    snapshot.metadata.description
                    or f"A repository classified as {', '.join(project_types).lower()}."
                ),
                languages=self.language_analyzer.analyze(snapshot),
                technologies=technologies,
                important_files=self.important_file_analyzer.analyze(snapshot),
                project_types=project_types,
                dependencies=dependencies,
                runtimes=runtimes,
                quality=quality,
                scores=self.score_analyzer.analyze(quality),
                setup_steps=setup_steps,
                prerequisites=prerequisites,
                compatibility=compatibility,
                strengths=strengths,
                risks=risks,
                missing_essentials=missing_essentials,
                unknowns=unknowns,
            ),
        )

    @staticmethod
    def _project_types(snapshot: RepositorySnapshot, technologies: set[str]) -> list[str]:
        paths = {file.path.lower() for file in snapshot.files}
        types = []
        if technologies.intersection({"Next.js", "Vite", "Angular", "Svelte", "Astro", "Nuxt"}):
            types.append("Web application")
        if "dockerfile" in paths or "Docker" in technologies:
            types.append("Containerized application")
        if any(path.startswith(".github/workflows/") for path in paths):
            types.append("CI-enabled project")
        if not types:
            types.append("General software repository")
        return types

    @staticmethod
    def _merge_technologies(
        *groups: list[TechnologyFinding],
    ) -> list[TechnologyFinding]:
        merged: dict[tuple[str, str], TechnologyFinding] = {}
        for group in groups:
            for item in group:
                key = (item.name, item.category)
                existing = merged.get(key)
                if existing:
                    existing.evidence = sorted(set(existing.evidence + item.evidence))
                else:
                    merged[key] = item
        return sorted(merged.values(), key=lambda item: (item.category, item.name))
