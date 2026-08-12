import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.db.store import AnalysisPersistenceError, AnalysisStore, get_analysis_store
from app.observability import log_event

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
def readiness(
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> dict[str, str]:
    try:
        store.ping()
    except AnalysisPersistenceError as exc:
        log_event("database_failure", level=logging.ERROR, operation="readiness", status=503)
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
    return {"status": "ready", "database": "ok"}
