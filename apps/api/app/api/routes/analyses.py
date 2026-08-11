import re
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.analysis.pipeline import AnalysisPipeline
from app.auth import AuthUser, get_optional_user, require_user
from app.compatibility import MachineCompatibilityResult, MachineProfile, evaluate_machine
from app.core.config import get_settings
from app.db.store import (
    AnalysisPersistenceError,
    AnalysisStore,
    AnonymousLimitExceeded,
    AuthenticatedLimitExceeded,
    get_analysis_store,
)
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
from app.schemas.analysis import AnalysisHistoryItem, AnalysisReport
from app.schemas.repository import AnalysisRequest

router = APIRouter(prefix="/analyses", tags=["analyses"])
_ANONYMOUS_ID = re.compile(r"^[A-Za-z0-9_-]{20,128}$")
_PUBLIC_ID = re.compile(r"^[A-Za-z0-9_-]{8,32}$")


def get_repository_provider() -> RepositoryProvider:
    return GitHubRepositoryProvider()


@router.post("", response_model=AnalysisReport, status_code=status.HTTP_200_OK)
async def request_analysis(
    payload: AnalysisRequest,
    request: Request,
    response: Response,
    provider: Annotated[RepositoryProvider, Depends(get_repository_provider)],
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
    user: Annotated[AuthUser | None, Depends(get_optional_user)],
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
        headers = {"Retry-After": str(exc.retry_after_seconds)} if exc.retry_after_seconds else None
        raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
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
    candidate_id = request.cookies.get("repolive_anonymous_id", "")
    anonymous_id = (
        candidate_id if _ANONYMOUS_ID.fullmatch(candidate_id) else secrets.token_urlsafe(24)
    )
    try:
        stored_report = store.save(
            report,
            anonymous_id,
            get_settings().free_anonymous_analysis_limit,
            user.user_id if user else None,
            get_settings().free_authenticated_analysis_limit,
        )
    except AnonymousLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Anonymous analysis allowance exhausted.",
        ) from exc
    except AuthenticatedLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Authenticated new-analysis allowance exhausted. Cached reports remain reusable."
            ),
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


@router.get("/me/history", response_model=list[AnalysisHistoryItem])
def get_analysis_history(
    user: Annotated[AuthUser, Depends(require_user)],
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> list[AnalysisHistoryItem]:
    return [AnalysisHistoryItem.model_validate(item) for item in store.list_for_user(user.user_id)]


@router.delete("/me/history/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis_history_item(
    public_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> Response:
    if not _PUBLIC_ID.fullmatch(public_id):
        raise HTTPException(status_code=404, detail="Saved analysis not found.")
    if not store.remove_for_user(user.user_id, public_id):
        raise HTTPException(status_code=404, detail="Saved analysis not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{public_id}/compatibility", response_model=MachineCompatibilityResult)
def check_machine_compatibility(
    public_id: str,
    machine: MachineProfile,
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> MachineCompatibilityResult:
    if not _PUBLIC_ID.fullmatch(public_id):
        raise HTTPException(status_code=404, detail="Analysis not found.")
    report = store.get(public_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return evaluate_machine(report, machine)


@router.get("/{public_id}", response_model=AnalysisReport)
def get_analysis(
    public_id: str,
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> AnalysisReport:
    if not _PUBLIC_ID.fullmatch(public_id):
        raise HTTPException(status_code=404, detail="Analysis not found.")
    report = store.get(public_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return report
