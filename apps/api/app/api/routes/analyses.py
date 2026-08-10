from fastapi import APIRouter, HTTPException, status

from app.providers.base import InvalidRepositoryUrl
from app.providers.github import GitHubRepositoryProvider
from app.schemas.repository import AnalysisAccepted, AnalysisRequest

router = APIRouter(prefix="/analyses", tags=["analyses"])
provider = GitHubRepositoryProvider()


@router.post("", response_model=AnalysisAccepted, status_code=status.HTTP_202_ACCEPTED)
def request_analysis(payload: AnalysisRequest) -> AnalysisAccepted:
    try:
        repository = provider.parse_url(payload.repository_url)
    except InvalidRepositoryUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnalysisAccepted(
        repository=repository,
        status="validated",
        message="Repository URL validated. Remote ingestion is the next milestone.",
    )

