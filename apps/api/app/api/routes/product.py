import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.analysis.comparison import compare_reports
from app.analysis.diagnosis import diagnose_error
from app.api.routes.analyses import get_repository_provider
from app.db.store import AnalysisStore, get_analysis_store
from app.observability import log_event
from app.providers.base import (
    RepositoryConnectivityError,
    RepositoryProviderError,
    RepositoryRateLimitError,
)
from app.providers.github import GitHubRepositoryProvider
from app.schemas.analysis import AnalysisReport
from app.schemas.product import (
    ComparisonRequest,
    DiscoveryResponse,
    ErrorDiagnosis,
    ErrorDiagnosisRequest,
    RepositoryComparison,
)

router = APIRouter(tags=["product tools"])
_PUBLIC_ID = re.compile(r"^[A-Za-z0-9_-]{8,32}$")
_FILTER = re.compile(r"^[A-Za-z0-9_.+ -]{1,40}$")


@router.post("/analyses/{public_id}/diagnose", response_model=ErrorDiagnosis)
def diagnose_repository_error(
    public_id: str,
    payload: ErrorDiagnosisRequest,
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> ErrorDiagnosis:
    report = _report_or_404(store, public_id)
    result = diagnose_error(payload.error_text, report)
    log_event(
        "error_diagnosed",
        analysis_id=public_id,
        category=result.category,
        confidence=result.confidence,
    )
    return result


@router.post("/comparisons", response_model=RepositoryComparison)
def compare_repositories(
    payload: ComparisonRequest,
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> RepositoryComparison:
    left = _report_or_404(store, payload.left_public_id)
    right = _report_or_404(store, payload.right_public_id)
    result = compare_reports(left, right)
    log_event(
        "repositories_compared", left_analysis_id=left.public_id, right_analysis_id=right.public_id
    )
    return result


@router.get("/discover", response_model=DiscoveryResponse)
async def discover_repositories(
    provider: Annotated[GitHubRepositoryProvider, Depends(get_repository_provider)],
    topic: Annotated[str | None, Query(max_length=40)] = None,
    language: Annotated[str | None, Query(max_length=40)] = None,
    project_type: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=10)] = 6,
) -> DiscoveryResponse:
    filters = {"topic": topic, "language": language, "project_type": project_type}
    if not any(filters.values()):
        raise HTTPException(status_code=422, detail="Provide a topic, language, or project type.")
    if any(value and not _FILTER.fullmatch(value) for value in filters.values()):
        raise HTTPException(
            status_code=422, detail="Search filters contain unsupported characters."
        )
    query_parts = []
    if topic:
        query_parts.append(f"topic:{topic.replace(' ', '-').lower()}")
    if language:
        query_parts.append(f"language:{language}")
    if project_type:
        query_parts.append(project_type)
    query = " ".join(query_parts)
    try:
        items = await provider.search_repositories(query, limit)
    except RepositoryRateLimitError as exc:
        headers = {"Retry-After": str(exc.retry_after_seconds)} if exc.retry_after_seconds else None
        log_event("github_search_failure", reason="rate_limited", status=429)
        raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
    except RepositoryConnectivityError as exc:
        log_event("github_search_failure", reason="connectivity", status=504)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RepositoryProviderError as exc:
        log_event("github_search_failure", reason="provider_error", status=502)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    log_event(
        "repositories_discovered", result_count=len(items), query_filter_count=len(query_parts)
    )
    return DiscoveryResponse(query=query, items=items)


def _report_or_404(store: AnalysisStore, public_id: str) -> AnalysisReport:
    if not _PUBLIC_ID.fullmatch(public_id):
        raise HTTPException(status_code=404, detail="Analysis not found.")
    report = store.get(public_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return report
