import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.analysis.pipeline import AnalysisPipeline
from app.core.config import get_settings
from app.db.store import AnalysisPersistenceError, AnalysisStore, AnonymousLimitExceeded
from app.providers.base import (
    InvalidRepositoryUrl,
    RepositoryConnectivityError,
    RepositoryNotFoundError,
    RepositoryProvider,
    RepositoryProviderError,
    RepositoryRateLimitError,
    RepositoryTooLargeError,
)
from app.providers.github import GitHubRepositoryProvider
from app.schemas.analysis import AnalysisReport
from app.schemas.repository import AnalysisRequest

router = APIRouter(prefix="/analyses", tags=["analyses"])


def get_repository_provider() -> RepositoryProvider:
    return GitHubRepositoryProvider()


@lru_cache
def get_analysis_store() -> AnalysisStore:
    settings = get_settings()
    return AnalysisStore(settings.database_url, create_schema=settings.app_env != "production")


@router.post("", response_model=AnalysisReport, status_code=status.HTTP_200_OK)
async def request_analysis(
    payload: AnalysisRequest,
    request: Request,
    response: Response,
    provider: Annotated[RepositoryProvider, Depends(get_repository_provider)],
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> AnalysisReport:
    try:
        repository = provider.parse_url(payload.repository_url)
    except InvalidRepositoryUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        snapshot = await provider.fetch_snapshot(repository)
    except RepositoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except RepositoryTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except RepositoryConnectivityError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RepositoryProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    report = (
        AnalysisPipeline()
        .analyze(snapshot)
        .model_copy(update={"analysis_version": get_settings().analysis_version})
    )
    anonymous_id = request.cookies.get("repolive_anonymous_id") or secrets.token_urlsafe(24)
    try:
        stored_report = store.save(
            report, anonymous_id, get_settings().free_anonymous_analysis_limit
        )
    except AnonymousLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Anonymous analysis allowance exhausted.",
        ) from exc
    except AnalysisPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis completed but could not be persisted. Please retry.",
        ) from exc
    response.set_cookie(
        "repolive_anonymous_id",
        anonymous_id,
        httponly=True,
        secure=get_settings().app_env == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
    )
    return stored_report


@router.get("/{public_id}", response_model=AnalysisReport)
def get_analysis(
    public_id: str,
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> AnalysisReport:
    if len(public_id) > 32:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    report = store.get(public_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return report
