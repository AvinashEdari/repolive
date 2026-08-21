from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import AuthUser, require_user
from app.core.config import Settings, get_settings
from app.db.store import AnalysisStore, get_analysis_store
from app.previews.models import PreviewEvent, PreviewPolicyResult, PreviewStatus, PreviewView
from app.previews.policy import PreviewPolicy
from app.previews.store import PreviewConflict, PreviewQuotaExceeded, PreviewStore

router = APIRouter(tags=["previews"])


def preview_store(store: Annotated[AnalysisStore, Depends(get_analysis_store)]) -> PreviewStore:
    return PreviewStore(store)


@router.get("/preview-capabilities")
def capabilities(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    return {
        "available": settings.preview_execution_enabled,
        "profiles": [
            "static_html_v1",
            "node_vite_v1",
            "node_vite_tsc_v1",
            "node_vite_tsc_noemit_v1",
            "node_cra_v1",
            "python_flask_app_v1",
            "node_next_server_v1",
            "node_express_server_v1",
            "node_express_app_v1",
            "node_express_index_v1",
            "python_fastapi_main_v1",
            "python_django_manage_v1",
            "python_streamlit_app_v1",
        ],
        "authentication_required": True,
        "local_auth_bypass": settings.app_env == "development"
        and settings.preview_local_auth_bypass,
        "arbitrary_commands": False,
        "runtime_provider": settings.preview_runtime_provider
        if settings.preview_execution_enabled
        else "disabled",
    }


@router.get("/analyses/{public_id}/preview-policy", response_model=PreviewPolicyResult)
def policy(
    public_id: str,
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PreviewPolicyResult:
    report = store.get(public_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return PreviewPolicy(settings).evaluate(report)


@router.post(
    "/analyses/{public_id}/previews",
    response_model=PreviewView,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_preview(
    public_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PreviewView:
    if not settings.preview_execution_enabled:
        raise HTTPException(status_code=503, detail="Preview execution is not configured.")
    report = store.get(public_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    decision = PreviewPolicy(settings).evaluate(report)
    if decision.decision != "eligible" or decision.detected_profile is None:
        raise HTTPException(
            status_code=422, detail="This repository is not eligible for a preview."
        )
    previews = PreviewStore(store)
    try:
        result = previews.create(
            public_id,
            user.user_id,
            decision.detected_profile,
            PreviewPolicy.VERSION,
            settings.preview_period_limit,
            settings.preview_max_concurrent_per_user,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found in your account.") from exc
    except PreviewConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PreviewQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    previews.transition(result.preview_id, PreviewStatus.POLICY_CHECK, "Preview policy approved.")
    previews.transition(
        result.preview_id,
        PreviewStatus.QUEUED,
        "Preview queued for an isolated worker.",
        queued_at=datetime.now(UTC),
    )
    return previews.get(result.preview_id, user.user_id)


@router.get("/previews/{preview_id}", response_model=PreviewView)
def get_preview(
    preview_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    previews: Annotated[PreviewStore, Depends(preview_store)],
) -> PreviewView:
    try:
        return previews.get(preview_id, user.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preview not found.") from exc


@router.get("/previews/{preview_id}/events", response_model=list[PreviewEvent])
def get_events(
    preview_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    previews: Annotated[PreviewStore, Depends(preview_store)],
) -> list[PreviewEvent]:
    try:
        return previews.events(preview_id, user.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preview not found.") from exc


@router.post("/previews/{preview_id}/stop", status_code=status.HTTP_202_ACCEPTED)
def stop_preview(
    preview_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    previews: Annotated[PreviewStore, Depends(preview_store)],
) -> Response:
    try:
        current = previews.get(preview_id, user.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preview not found.") from exc
    if current.status in {
        PreviewStatus.CANCELED,
        PreviewStatus.DESTROYED,
        PreviewStatus.EXPIRED,
        PreviewStatus.REJECTED,
        PreviewStatus.FAILED,
        PreviewStatus.TIMED_OUT,
    }:
        return Response(status_code=202)
    target = (
        PreviewStatus.STOPPING if current.status == PreviewStatus.READY else PreviewStatus.CANCELED
    )
    if not previews.transition(preview_id, target, "Preview stop requested."):
        raise HTTPException(
            status_code=409, detail="Preview cannot be stopped from its current state."
        )
    return Response(status_code=202)


@router.post(
    "/previews/{preview_id}/retry", response_model=PreviewView, status_code=status.HTTP_202_ACCEPTED
)
def retry_preview(
    preview_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    previews: Annotated[PreviewStore, Depends(preview_store)],
) -> PreviewView:
    try:
        current = previews.get(preview_id, user.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preview not found.") from exc
    if not current.retryable or not previews.retry(preview_id):
        raise HTTPException(status_code=409, detail="Preview is not retryable.")
    return previews.get(preview_id, user.user_id)
