from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.repository import RepositorySnapshot

TechnologyCategory = Literal["framework", "build_tool", "infrastructure", "package_manager"]
DependencyScope = Literal["runtime", "development", "optional", "unknown"]


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


class DeterministicAnalysis(BaseModel):
    languages: list[LanguageFinding]
    technologies: list[TechnologyFinding]
    important_files: list[ImportantFileFinding]
    project_types: list[str]
    dependencies: list[DependencyFinding]
    runtimes: list[RuntimeFinding]
    quality: QualitySignals
    scores: list[ExplainableScore]


class AnalysisReport(BaseModel):
    public_id: str | None = None
    snapshot: RepositorySnapshot
    analysis: DeterministicAnalysis
    status: Literal["analyzed"] = "analyzed"
