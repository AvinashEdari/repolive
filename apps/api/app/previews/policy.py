from app.core.config import Settings
from app.previews.models import PreviewLimits, PreviewPolicyResult
from app.schemas.analysis import AnalysisReport


class PreviewPolicy:
    VERSION = "static-v1"

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
        )
        dangerous = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"} & paths
        if "index.html" in paths and not dangerous:
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
        reasons = ["Stage 1 supports only a root index.html served without a build command."]
        if dangerous:
            reasons.append(
                "Container manifests are never executed and make this profile ineligible."
            )
        return PreviewPolicyResult(decision="ineligible", reasons=reasons, limits=limits)
