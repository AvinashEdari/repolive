from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.providers.base import InvalidRepositoryUrl, RepositoryProvider, RepositoryProviderError
from app.providers.github import GitHubRepositoryProvider
from app.schemas.repository import AnalysisRequest, RepositorySnapshot

router = APIRouter(prefix="/analyses", tags=["analyses"])


def get_repository_provider() -> RepositoryProvider:
    return GitHubRepositoryProvider()


@router.post("", response_model=RepositorySnapshot, status_code=status.HTTP_200_OK)
async def request_analysis(
    payload: AnalysisRequest,
    provider: Annotated[RepositoryProvider, Depends(get_repository_provider)],
) -> RepositorySnapshot:
    try:
        repository = provider.parse_url(payload.repository_url)
    except InvalidRepositoryUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return await provider.fetch_snapshot(repository)
    except RepositoryProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
