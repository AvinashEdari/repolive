import re
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analysis import AnalysisReport

CompatibilityStatus = Literal["compatible", "probably_compatible", "incompatible", "unknown"]


class MachineProfile(BaseModel):
    operating_system: Literal["Windows", "Linux", "macOS"]
    cpu_architecture: Literal["x86_64", "arm64", "x86"]
    ram_gib: float | None = Field(default=None, gt=0, le=4096)
    storage_gib: float | None = Field(default=None, gt=0, le=1_000_000)
    gpu: str | None = Field(default=None, max_length=100)
    gpu_vram_gib: float | None = Field(default=None, gt=0, le=1024)
    python_version: str | None = Field(default=None, pattern=r"^\d+(\.\d+){0,2}$")
    node_version: str | None = Field(default=None, pattern=r"^\d+(\.\d+){0,2}$")
    java_version: str | None = Field(default=None, pattern=r"^\d+(\.\d+){0,2}$")
    docker_available: bool | None = None


class MachineCondition(BaseModel):
    subject: str
    status: CompatibilityStatus
    detail: str
    evidence: list[str]


class MachineCompatibilityResult(BaseModel):
    status: CompatibilityStatus
    conditions: list[MachineCondition]
    summary: str


def evaluate_machine(report: AnalysisReport, machine: MachineProfile) -> MachineCompatibilityResult:
    conditions: list[MachineCondition] = []
    versions = {
        "python": machine.python_version,
        "node.js": machine.node_version,
        "java": machine.java_version,
    }
    for runtime in report.analysis.runtimes:
        provided = versions.get(runtime.runtime.lower())
        if provided is None:
            conditions.append(
                MachineCondition(
                    subject=runtime.runtime,
                    status="unknown",
                    detail="Installed version was not provided.",
                    evidence=runtime.evidence,
                )
            )
            continue
        compatible = _meets_constraint(provided, runtime.version_constraint)
        conditions.append(
            MachineCondition(
                subject=runtime.runtime,
                status="compatible" if compatible else "incompatible",
                detail=(
                    f"Installed {provided}; repository declares "
                    f"{runtime.version_constraint or 'no exact version constraint'}."
                ),
                evidence=runtime.evidence,
            )
        )
    platforms = [
        item for item in report.analysis.compatibility if item.subject == "Operating system"
    ]
    if platforms:
        item = platforms[0]
        declared = {name for name in ("Windows", "Linux", "macOS") if name in item.detail}
        conditions.append(
            MachineCondition(
                subject="Operating system",
                status="compatible"
                if not declared or machine.operating_system in declared
                else "incompatible",
                detail=f"Machine uses {machine.operating_system}. {item.detail}",
                evidence=item.evidence,
            )
        )
    container_files = [
        item.path for item in report.analysis.important_files if "docker" in item.path.lower()
    ]
    if container_files and machine.docker_available is not None:
        conditions.append(
            MachineCondition(
                subject="Docker",
                status="compatible" if machine.docker_available else "probably_compatible",
                detail="Docker configuration exists; Docker is available."
                if machine.docker_available
                else (
                    "Docker configuration exists, but Docker was reported unavailable. "
                    "A non-container setup may still work."
                ),
                evidence=container_files,
            )
        )
    if not conditions:
        return MachineCompatibilityResult(
            status="unknown",
            conditions=[],
            summary=(
                "The repository does not declare enough machine requirements for a "
                "deterministic comparison."
            ),
        )
    statuses = {item.status for item in conditions}
    overall: CompatibilityStatus = (
        "incompatible"
        if "incompatible" in statuses
        else "unknown"
        if statuses == {"unknown"}
        else "probably_compatible"
        if "unknown" in statuses or "probably_compatible" in statuses
        else "compatible"
    )
    return MachineCompatibilityResult(
        status=overall,
        conditions=conditions,
        summary=(
            "Compatibility is based only on explicit repository evidence and the machine "
            "details supplied by the user."
        ),
    )


def _meets_constraint(provided: str, constraint: str | None) -> bool:
    if not constraint:
        return True
    required = re.search(r"(\d+(?:\.\d+){0,2})", constraint)
    if not required:
        return True
    left = tuple(int(part) for part in provided.split("."))
    right = tuple(int(part) for part in required.group(1).split("."))
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    if any(marker in constraint for marker in (">=", "^", "~", ">")):
        return left >= right
    if "<" in constraint and ">" not in constraint:
        return left < right
    return left == right
