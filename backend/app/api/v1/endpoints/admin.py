from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_admin_overview_service,
    get_admin_service,
)
from app.api.middleware import metrics_snapshot
from app.schemas import AdminClearIndexRequest, AdminClearIndexResponse, AdminOverviewResponse
from app.services import AdminOverviewService, AdminService

router = APIRouter()


@router.post("/index/clear", response_model=AdminClearIndexResponse)
def clear_index(
    request: AdminClearIndexRequest,
    service: AdminService = Depends(get_admin_service),
) -> AdminClearIndexResponse:
    stats = service.clear_index(confirm=request.confirm)
    return AdminClearIndexResponse(
        status="cleared",
        document_count=stats.document_count,
        parent_chunk_count=stats.parent_chunk_count,
        child_chunk_count=stats.child_chunk_count,
    )


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    service: AdminOverviewService = Depends(get_admin_overview_service),
) -> AdminOverviewResponse:
    """
    Returns database-backed data for the admin overview dashboard.
    """

    return service.build()


@router.get("/metrics")
def get_api_metrics() -> dict:
    return metrics_snapshot()
