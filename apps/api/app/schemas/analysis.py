from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.repository import RepositorySnapshot

TechnologyCategory = Literal["framework", "build_tool", "infrastructure", "package_manager"]
DependencyScope = Literal["runtime", "development", "optional", "unknown"]
Platform = Literal["Windows", "Linux", "macOS"]


class LanguageFinding(BaseModel):
    name: str
    file_count: int = Field(ge=1)
    known_bytes: int = Field(ge=0)
    share_percent: float = Field(ge=0, le=100)
    evidence: list[str]


class TechnologyFinding(BaseModel):
    name: str
    category: TechnologyCategory
    confidence: Literal["high", "medium"]
    evidence: list[str]


class ImportantFileFinding(BaseModel):
    path: str
    role: str


class DependencyFinding(BaseModel):
    name: str
    version_constraint: str | None
    scope: DependencyScope
    ecosystem: str
    source_path: str


class RuntimeFinding(BaseModel):
    runtime: str
    version_constraint: str | None
    evidence: list[str]


class QualitySignals(BaseModel):
    has_readme: bool
    has_license: bool
    has_tests: bool
    has_ci: bool
    has_container_config: bool
    has_environment_example: bool


class ScoreFactor(BaseModel):
    label: str
    impact: Literal["positive", "negative", "neutral"]
    evidence: list[str]


class ExplainableScore(BaseModel):
    name: str
    value: int = Field(ge=0, le=100)
    factors: list[ScoreFactor]


class SetupStep(BaseModel):
    title: str
    command: str | None
    origin: Literal["repository", "derived"]
    source_path: str
    platforms: list[Platform]


class PrerequisiteFinding(BaseModel):
    name: str
    version_constraint: str | None
    confidence: Literal["high", "medium"]
    evidence: list[str]


class CompatibilityFinding(BaseModel):
    subject: str
    status: Literal["compatible", "conditional", "unknown"]
    detail: str
    evidence: list[str]


class InsightFinding(BaseModel):
    label: str
    evidence: list[str]


class ExplanationResult(BaseModel):
    enabled: bool
    provider: str
    summary: str
    label: Literal["deterministic fallback", "optional explanation"]


class DeterministicAnalysis(BaseModel):
    purpose_summary: str = "Repository purpose is not declared."
    languages: list[LanguageFinding]
    technologies: list[TechnologyFinding]
    important_files: list[ImportantFileFinding]
    project_types: list[str]
    dependencies: list[DependencyFinding]
    runtimes: list[RuntimeFinding]
    quality: QualitySignals
    scores: list[ExplainableScore]
    setup_steps: list[SetupStep] = Field(default_factory=list)
    prerequisites: list[PrerequisiteFinding] = Field(default_factory=list)
    compatibility: list[CompatibilityFinding] = Field(default_factory=list)
    strengths: list[InsightFinding] = Field(default_factory=list)
    risks: list[InsightFinding] = Field(default_factory=list)
    missing_essentials: list[InsightFinding] = Field(default_factory=list)
    unknowns: list[InsightFinding] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    public_id: str | None = None
    analysis_version: str = "1"
    snapshot: RepositorySnapshot
    analysis: DeterministicAnalysis
    explanation: ExplanationResult = ExplanationResult(
        enabled=False,
        provider="disabled",
        summary="Optional explanations are disabled; deterministic findings remain available.",
        label="deterministic fallback",
    )
    status: Literal["analyzed"] = "analyzed"
