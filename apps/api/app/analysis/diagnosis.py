import re
from dataclasses import dataclass

from app.schemas.analysis import AnalysisReport
from app.schemas.product import ErrorDiagnosis


@dataclass(frozen=True)
class Rule:
    category: str
    label: str
    patterns: tuple[str, ...]
    checks: tuple[str, ...]


_RULES = (
    Rule(
        "missing_environment_variable",
        "Missing environment variable",
        (
            r"(?:environment variable|env var|keyerror)[: '\"]+([A-Z][A-Z0-9_]{2,})",
            r"([A-Z][A-Z0-9_]{2,}) (?:is not set|is required|missing)",
        ),
        (
            "Compare required variable names with the repository's example environment file.",
            "Confirm the variable is set in the same terminal or service that starts "
            "the application.",
        ),
    ),
    Rule(
        "missing_dependency",
        "Missing dependency",
        (
            r"no module named ['\"]?([A-Za-z0-9_.-]+)",
            r"cannot find (?:module|package) ['\"]?([^'\"\s]+)",
            r"modulenotfounderror",
        ),
        (
            "Check whether the named package appears in the detected dependency manifests.",
            "Use the repository's documented package-manager workflow; review commands "
            "before running them.",
        ),
    ),
    Rule(
        "missing_executable",
        "Missing executable",
        (
            r"(?:command not found|is not recognized as an internal|executable file not found)"
            r"[: ]*([^\r\n]{0,80})",
            r"enoent",
        ),
        (
            "Confirm the required runtime or tool is installed and available on PATH.",
            "Check the repository runtime and prerequisite sections for the expected tool.",
        ),
    ),
    Rule(
        "incompatible_runtime",
        "Incompatible runtime version",
        (
            r"(?:unsupported|requires?|expected).{0,40}(?:python|node|java|ruby|go|rust|php|\.net).{0,30}(\d+(?:\.\d+){0,2})",
            r"syntaxerror",
        ),
        (
            "Compare the installed runtime version with the repository's declared constraint.",
            "Use an isolated runtime environment before changing a system-wide installation.",
        ),
    ),
    Rule(
        "package_manager_issue",
        "Package-manager issue",
        (
            r"npm err!",
            r"yarn error",
            r"pnpm.+error",
            r"pip.+(?:failed|error)",
            r"dependency resolution",
        ),
        (
            "Confirm the repository's expected package manager and lockfile.",
            "Review the first package-manager error before retrying; later lines are often "
            "consequences.",
        ),
    ),
    Rule(
        "permission_issue",
        "Permission issue",
        (r"permission denied", r"eacces", r"operation not permitted", r"access is denied"),
        (
            "Check ownership and permissions only for the specific path named by the error.",
            "Avoid administrator or root execution unless the repository explicitly "
            "requires and explains it.",
        ),
    ),
    Rule(
        "port_conflict",
        "Port conflict",
        (r"address already in use", r"eaddrinuse", r"port \d{2,5}.+(?:used|occupied)"),
        (
            "Identify which local process currently owns the reported port.",
            "Prefer changing the application's documented port setting over terminating "
            "unrelated services.",
        ),
    ),
    Rule(
        "database_connection_failure",
        "Database connection failure",
        (
            r"connection refused.{0,80}(?:database|postgres|mysql|redis|mongo)",
            r"(?:database|postgres|mysql|redis|mongo).{0,80}"
            r"(?:unavailable|connection failed|timeout)",
        ),
        (
            "Verify the database service is running and reachable from the application "
            "environment.",
            "Check host, port, database name, TLS mode, and credentials without sharing "
            "their values.",
        ),
    ),
    Rule(
        "missing_system_library",
        "Missing system library",
        (
            r"cannot open shared object file",
            r"dll load failed",
            r"library not loaded",
            r"ld: library not found",
        ),
        (
            "Identify the exact library name and the operating-system package that provides it.",
            "Confirm the library architecture matches the runtime architecture.",
        ),
    ),
    Rule(
        "network_download_problem",
        "Network or download problem",
        (
            r"(?:connection|read) timed out",
            r"could not resolve host",
            r"temporary failure in name resolution",
            r"certificate verify failed",
            r"network is unreachable",
        ),
        (
            "Check connectivity, DNS, proxy, and provider status without disabling TLS "
            "verification.",
            "Retry only after checking provider rate limits and the earliest network error.",
        ),
    ),
)


def diagnose_error(error_text: str, report: AnalysisReport) -> ErrorDiagnosis:
    normalized = error_text.strip()
    for rule in _RULES:
        for pattern in rule.patterns:
            match = re.search(pattern, normalized, re.IGNORECASE | re.DOTALL)
            if match:
                evidence = [f"Error pattern matched: {rule.label}."]
                context = _context_evidence(rule.category, match, report)
                evidence.extend(context)
                return ErrorDiagnosis(
                    category=rule.category,  # type: ignore[arg-type]
                    label=rule.label,
                    confidence="high" if context else "medium",
                    evidence=evidence,
                    safe_next_checks=list(rule.checks),
                    unknowns=_unknowns(report),
                )
    return ErrorDiagnosis(
        category="unknown",
        label="No supported deterministic category matched",
        confidence="low",
        evidence=["The supplied text did not match a bounded supported error signature."],
        safe_next_checks=[
            "Find the earliest error line and the operation that immediately preceded it.",
            "Compare the failure with the repository's runtime, setup, and prerequisite evidence.",
        ],
        unknowns=_unknowns(report) + ["The root cause cannot be classified from this text alone."],
    )


def _context_evidence(category: str, match: re.Match[str], report: AnalysisReport) -> list[str]:
    analysis = report.analysis
    evidence: list[str] = []
    captured = match.group(1).lower() if match.lastindex and match.group(1) else ""
    if category == "missing_dependency" and captured:
        for dependency in analysis.dependencies:
            if captured.split(".")[0] in dependency.name.lower():
                evidence.append(
                    f"Repository dependency evidence: {dependency.name} in "
                    f"{dependency.source_path}."
                )
                break
    if category == "missing_environment_variable" and captured:
        for prerequisite in analysis.prerequisites:
            if captured in prerequisite.name.lower():
                evidence.append(f"Repository prerequisite evidence: {prerequisite.name}.")
                break
    if category in {"missing_executable", "incompatible_runtime"} and analysis.runtimes:
        evidence.extend(
            f"Declared runtime: {item.runtime} "
            f"{item.version_constraint or '(version unspecified)'} from "
            f"{', '.join(item.evidence)}."
            for item in analysis.runtimes[:3]
        )
    if category == "package_manager_issue":
        managers = [item for item in analysis.technologies if item.category == "package_manager"]
        evidence.extend(f"Detected package manager: {item.name}." for item in managers[:2])
    return evidence


def _unknowns(report: AnalysisReport) -> list[str]:
    unknowns = [
        "The local operating system, command, working directory, and preceding actions "
        "were not independently verified."
    ]
    if not report.analysis.runtimes:
        unknowns.append("The repository does not declare a supported runtime constraint.")
    return unknowns
