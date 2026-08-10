from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.repository import RepositorySnapshot

TechnologyCategory = Literal["framework", "build_tool", "infrastructure", "package_manager"]


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


class DeterministicAnalysis(BaseModel):
    languages: list[LanguageFinding]
    technologies: list[TechnologyFinding]
    important_files: list[ImportantFileFinding]
    project_types: list[str]


class AnalysisReport(BaseModel):
    snapshot: RepositorySnapshot
    analysis: DeterministicAnalysis
    status: Literal["analyzed"] = "analyzed"
