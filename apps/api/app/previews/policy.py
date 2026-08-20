from app.core.config import Settings
from app.previews.models import PreviewLimits, PreviewPolicyResult
from app.schemas.analysis import AnalysisReport


class PreviewPolicy:
    VERSION = "frontend-v1"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(self, report: AnalysisReport) -> PreviewPolicyResult:
        paths = {item.path for item in report.snapshot.files}
        limits = PreviewLimits(
            cpu_count=self.settings.preview_cpu_count,
            memory_mb=self.settings.preview_memory_mb,
            pids=self.settings.preview_pids_limit,
            build_timeout_seconds=self.settings.preview_build_timeout_seconds,
            runtime_seconds=self.settings.preview_runtime_seconds,
            log_bytes=self.settings.preview_log_bytes,
            repository_files=self.settings.max_repository_files,
            repository_bytes=self.settings.max_repository_bytes,
        )
        dangerous = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"} & paths
        if "index.html" in paths and "package.json" not in paths and not dangerous:
            return PreviewPolicyResult(
                decision="eligible",
                detected_profile="static_html_v1",
                reasons=["A root index.html was found."],
                required_runtime="repolive/static-server:1",
                proposed_build_command=[],
                expected_output_directory=".",
                expected_application_port=8080,
                limits=limits,
                warnings=["Local Docker isolation is development-only."],
            )
        package_files = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"} & paths
        if "package.json" in paths and package_files == {"package-lock.json"}:
            dependency_names = {
                item.name.casefold()
                for item in report.analysis.dependencies
                if item.ecosystem == "npm" and item.source_path == "package.json"
            }
            build_script = next(
                (
                    item.command
                    for item in report.analysis.setup_steps
                    if item.title == "Repository script: build"
                    and item.source_path == "package.json"
                    and item.command is not None
                ),
                None,
            )
            profile: tuple[str, str, str] | None = None
            if build_script == "vite build" and "vite" in dependency_names:
                profile = ("node_vite_v1", "dist", "Vite")
            elif (
                build_script == "tsc && vite build"
                and "vite" in dependency_names
                and "typescript" in dependency_names
            ):
                profile = ("node_vite_tsc_v1", "dist", "Vite with TypeScript")
            elif (
                build_script == "tsc --noEmit && vite build"
                and "vite" in dependency_names
                and "typescript" in dependency_names
            ):
                profile = ("node_vite_tsc_noemit_v1", "dist", "Vite with TypeScript")
            elif build_script == "react-scripts build" and "react-scripts" in dependency_names:
                profile = ("node_cra_v1", "build", "Create React App")
            if profile:
                profile_name, output_directory, framework = profile
                assert build_script is not None
                return PreviewPolicyResult(
                    decision="eligible",
                    detected_profile=profile_name,
                    reasons=[f"A locked {framework} static frontend was detected."],
                    required_runtime="Node.js 22",
                    package_manager="npm",
                    proposed_build_command=["npm ci", build_script],
                    expected_output_directory=output_directory,
                    expected_application_port=8080,
                    limits=limits,
                    warnings=[
                        "Dependency installation has build-time internet access.",
                        "Local Docker isolation is development-only.",
                    ],
                )
        python_dependencies = {
            item.name.casefold()
            for item in report.analysis.dependencies
            if item.ecosystem == "PyPI" and item.source_path == "requirements.txt"
        }
        if (
            {"app.py", "requirements.txt"}.issubset(paths)
            and "flask" in python_dependencies
            and not dangerous
        ):
            return PreviewPolicyResult(
                decision="eligible",
                detected_profile="python_flask_app_v1",
                reasons=["A root Flask application with declared dependencies was detected."],
                required_runtime="Python 3.11",
                package_manager="pip",
                proposed_build_command=["python -m pip install -r requirements.txt"],
                expected_output_directory=".",
                expected_application_port=8080,
                limits=limits,
                warnings=[
                    "Only the fixed root app:app Flask entry point is supported.",
                    "Runtime outbound network access is disabled.",
                    "Local Docker isolation is development-only.",
                ],
            )
        reasons = [
            "Supported previews require static HTML, a locked Vite/Create React App frontend, or a root Flask app."
        ]
        archives = sorted(path for path in paths if path.casefold().endswith((".zip", ".tar", ".gz")))
        if archives:
            reasons.insert(
                0,
                "Repository source is stored inside an archive, which preview workers do not extract or execute.",
            )
        if not ({"index.html", "package.json", "app.py"} & paths):
            reasons.append("No supported browser or server entry point was found at the repository root.")
        if dangerous:
            reasons.append(
                "Container manifests are never executed and make this profile ineligible."
            )
        return PreviewPolicyResult(decision="ineligible", reasons=reasons, limits=limits)
