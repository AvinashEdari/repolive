from app.analysis.languages import LanguageAnalyzer
from app.analysis.structure import ImportantFileAnalyzer, TechnologyAnalyzer
from app.schemas.analysis import AnalysisReport, DeterministicAnalysis
from app.schemas.repository import RepositorySnapshot


class AnalysisPipeline:
    def __init__(self) -> None:
        self.language_analyzer = LanguageAnalyzer()
        self.technology_analyzer = TechnologyAnalyzer()
        self.important_file_analyzer = ImportantFileAnalyzer()

    def analyze(self, snapshot: RepositorySnapshot) -> AnalysisReport:
        technologies = self.technology_analyzer.analyze(snapshot)
        project_types = self._project_types(snapshot, {item.name for item in technologies})
        return AnalysisReport(
            snapshot=snapshot,
            analysis=DeterministicAnalysis(
                languages=self.language_analyzer.analyze(snapshot),
                technologies=technologies,
                important_files=self.important_file_analyzer.analyze(snapshot),
                project_types=project_types,
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
