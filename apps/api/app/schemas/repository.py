from pydantic import BaseModel, Field


class RepositoryReference(BaseModel):
    provider: str = "github"
    owner: str = Field(min_length=1, max_length=39)
    name: str = Field(min_length=1, max_length=100)
    canonical_url: str


class AnalysisRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=500)


class AnalysisAccepted(BaseModel):
    repository: RepositoryReference
    status: str
    message: str

