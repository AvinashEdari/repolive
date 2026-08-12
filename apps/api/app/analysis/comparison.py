from statistics import mean

from app.schemas.analysis import AnalysisReport
from app.schemas.product import ComparisonDimension, RepositoryComparison


def compare_reports(left: AnalysisReport, right: AnalysisReport) -> RepositoryComparison:
    left_name = _name(left)
    right_name = _name(right)
    left_dependencies = {item.name.lower(): item.name for item in left.analysis.dependencies}
    right_dependencies = {item.name.lower(): item.name for item in right.analysis.dependencies}
    shared = sorted(left_dependencies.keys() & right_dependencies.keys())
    dimensions = [
        _dimension(
            "Purpose",
            left.analysis.purpose_summary,
            right.analysis.purpose_summary,
            "Repository descriptions and deterministic project classification.",
        ),
        _dimension(
            "Languages",
            _languages(left),
            _languages(right),
            "Languages are ordered by known source-byte share.",
        ),
        _dimension(
            "Frameworks and tools",
            _technologies(left),
            _technologies(right),
            "Only evidence-backed technologies are listed.",
        ),
        _dimension(
            "Setup difficulty",
            _setup(left),
            _setup(right),
            "A transparent heuristic using setup steps, runtimes, and missing essentials; "
            "it is not measured installation time.",
        ),
        _dimension(
            "Runtime requirements",
            _runtimes(left),
            _runtimes(right),
            "Explicitly declared runtime constraints only.",
        ),
        _dimension(
            "Tests",
            _yes_no(left.analysis.quality.has_tests),
            _yes_no(right.analysis.quality.has_tests),
            "Detected repository test signals.",
        ),
        _dimension(
            "CI",
            _yes_no(left.analysis.quality.has_ci),
            _yes_no(right.analysis.quality.has_ci),
            "Detected continuous-integration configuration.",
        ),
        _dimension(
            "Documentation",
            _yes_no(left.analysis.quality.has_readme),
            _yes_no(right.analysis.quality.has_readme),
            "README evidence and documentation score are considered separately.",
        ),
        _dimension(
            "Containers",
            _yes_no(left.analysis.quality.has_container_config),
            _yes_no(right.analysis.quality.has_container_config),
            "Detected container configuration.",
        ),
        _dimension(
            "Compatibility clues",
            str(len(left.analysis.compatibility)),
            str(len(right.analysis.compatibility)),
            "Count of evidence-backed compatibility conditions.",
        ),
        _dimension(
            "Health scores",
            _scores(left),
            _scores(right),
            "RepoLive's explainable documentation and engineering-readiness scores.",
        ),
        _dimension(
            "Strengths / risks",
            f"{len(left.analysis.strengths)} / {len(left.analysis.risks)}",
            f"{len(right.analysis.strengths)} / {len(right.analysis.risks)}",
            "Counts of deterministic strengths and risks.",
        ),
    ]
    return RepositoryComparison(
        left_public_id=str(left.public_id),
        right_public_id=str(right.public_id),
        left_repository=left_name,
        right_repository=right_name,
        dimensions=dimensions,
        shared_dependencies=[left_dependencies[key] for key in shared],
        left_only_dependencies=sorted(
            left_dependencies[key] for key in left_dependencies.keys() - right_dependencies.keys()
        ),
        right_only_dependencies=sorted(
            right_dependencies[key] for key in right_dependencies.keys() - left_dependencies.keys()
        ),
        summary=_summary(left, right, left_name, right_name),
        unknowns=[
            "Comparison reflects the analyzed commits and supported evidence only.",
            "No repository code or setup command was executed.",
        ],
    )


def _name(report: AnalysisReport) -> str:
    repository = report.snapshot.repository
    return f"{repository.owner}/{repository.name}"


def _dimension(name: str, left: str, right: str, explanation: str) -> ComparisonDimension:
    return ComparisonDimension(name=name, left=left, right=right, explanation=explanation)


def _languages(report: AnalysisReport) -> str:
    return (
        ", ".join(f"{item.name} {item.share_percent:g}%" for item in report.analysis.languages[:4])
        or "Unknown"
    )


def _technologies(report: AnalysisReport) -> str:
    return ", ".join(item.name for item in report.analysis.technologies[:8]) or "None detected"


def _runtimes(report: AnalysisReport) -> str:
    return (
        ", ".join(
            f"{item.runtime} {item.version_constraint or '(unspecified)'}"
            for item in report.analysis.runtimes
        )
        or "Unknown"
    )


def _scores(report: AnalysisReport) -> str:
    return (
        ", ".join(f"{item.name}: {item.value}" for item in report.analysis.scores) or "Unavailable"
    )


def _setup(report: AnalysisReport) -> str:
    weight = (
        len(report.analysis.setup_steps)
        + len(report.analysis.runtimes)
        + len(report.analysis.missing_essentials)
    )
    return "Lower" if weight <= 2 else "Moderate" if weight <= 5 else "Higher"


def _yes_no(value: bool) -> str:
    return "Detected" if value else "Not detected"


def _average_score(report: AnalysisReport) -> float | None:
    return mean(item.value for item in report.analysis.scores) if report.analysis.scores else None


def _summary(
    left: AnalysisReport, right: AnalysisReport, left_name: str, right_name: str
) -> list[str]:
    summary: list[str] = []
    left_score, right_score = _average_score(left), _average_score(right)
    if left_score is not None and right_score is not None:
        if left_score == right_score:
            summary.append("The repositories have the same average RepoLive health score.")
        else:
            winner = left_name if left_score > right_score else right_name
            summary.append(
                f"{winner} has the higher average RepoLive health score for these commits."
            )
    left_setup, right_setup = _setup(left), _setup(right)
    if left_setup != right_setup:
        summary.append(
            f"Setup heuristics differ: {left_name} is {left_setup.lower()}, while "
            f"{right_name} is {right_setup.lower()}."
        )
    return summary or ["No supported dimension produced a clear overall difference."]
