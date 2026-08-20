from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PreviewStatus(StrEnum):
    REQUESTED = "requested"
    POLICY_CHECK = "policy_check"
    QUEUED = "queued"
    CLONING = "cloning"
    BUILDING = "building"
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    DESTROYED = "destroyed"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    EXPIRED = "expired"
    CANCELED = "canceled"


TERMINAL_STATUSES = {
    PreviewStatus.DESTROYED,
    PreviewStatus.REJECTED,
    PreviewStatus.FAILED,
    PreviewStatus.TIMED_OUT,
    PreviewStatus.EXPIRED,
    PreviewStatus.CANCELED,
}
ALLOWED_TRANSITIONS: dict[PreviewStatus, set[PreviewStatus]] = {
    PreviewStatus.REQUESTED: {PreviewStatus.POLICY_CHECK, PreviewStatus.CANCELED},
    PreviewStatus.POLICY_CHECK: {
        PreviewStatus.QUEUED,
        PreviewStatus.REJECTED,
        PreviewStatus.CANCELED,
    },
    PreviewStatus.QUEUED: {PreviewStatus.CLONING, PreviewStatus.CANCELED, PreviewStatus.TIMED_OUT},
    PreviewStatus.CLONING: {
        PreviewStatus.BUILDING,
        PreviewStatus.FAILED,
        PreviewStatus.TIMED_OUT,
        PreviewStatus.CANCELED,
    },
    PreviewStatus.BUILDING: {
        PreviewStatus.STARTING,
        PreviewStatus.FAILED,
        PreviewStatus.TIMED_OUT,
        PreviewStatus.CANCELED,
    },
    PreviewStatus.STARTING: {
        PreviewStatus.READY,
        PreviewStatus.FAILED,
        PreviewStatus.TIMED_OUT,
        PreviewStatus.CANCELED,
    },
    PreviewStatus.READY: {PreviewStatus.STOPPING, PreviewStatus.EXPIRED, PreviewStatus.FAILED},
    PreviewStatus.STOPPING: {PreviewStatus.DESTROYED, PreviewStatus.FAILED},
    PreviewStatus.FAILED: {PreviewStatus.QUEUED},
    PreviewStatus.TIMED_OUT: {PreviewStatus.QUEUED},
}


class PreviewLimits(BaseModel):
    cpu_count: float
    memory_mb: int
    pids: int
    build_timeout_seconds: int
    runtime_seconds: int
    log_bytes: int
    repository_files: int = 10_000
    repository_bytes: int = 100 * 1024 * 1024


class PreviewPolicyResult(BaseModel):
    decision: str
    detected_profile: str | None = None
    reasons: list[str] = Field(default_factory=list)
    required_runtime: str | None = None
    package_manager: str | None = None
    proposed_build_command: list[str] | None = None
    expected_output_directory: str | None = None
    expected_application_port: int | None = None
    limits: PreviewLimits
    warnings: list[str] = Field(default_factory=list)


class PreviewEvent(BaseModel):
    event_id: str
    sequence: int
    event_type: str
    safe_message: str
    fields: dict[str, str | int | float | bool | None]
    created_at: datetime


class PreviewView(BaseModel):
    preview_id: str
    public_analysis_id: str
    status: PreviewStatus
    runtime_profile: str
    commit_sha: str
    requested_at: datetime
    started_at: datetime | None = None
    ready_at: datetime | None = None
    expires_at: datetime | None = None
    stopped_at: datetime | None = None
    destroyed_at: datetime | None = None
    safe_failure_message: str | None = None
    preview_url: str | None = None
    retryable: bool = False
