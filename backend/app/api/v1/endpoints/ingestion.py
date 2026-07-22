from __future__ import annotations

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
)

from app.api.dependencies import get_ingestion_service, get_task_executor
from app.schemas import (
    IngestionJobCreateResponse,
    IngestionJobListResponse,
    IngestionJobResponse,
)
from app.services import IngestionService, IngestionUploadOptions
from app.workers import TaskExecutor

router = APIRouter()


@router.post("/jobs", response_model=IngestionJobCreateResponse)
async def create_ingestion_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    clear_index: bool = Form(default=False),
    replace: bool = Form(default=True),
    continue_on_error: bool = Form(default=True),
    service: IngestionService = Depends(get_ingestion_service),
    task_executor: TaskExecutor = Depends(get_task_executor),
) -> IngestionJobCreateResponse:
    plan = await service.create_upload_job(
        files=files,
        options=IngestionUploadOptions(
            clear_index=clear_index,
            replace=replace,
            continue_on_error=continue_on_error,
        ),
    )
    if plan.run_in_background:
        task_executor.submit_ingestion_job(
            plan.job.id,
            add_background_task=background_tasks.add_task,
        )
    return IngestionJobCreateResponse(
        job=IngestionJobResponse.model_validate(plan.job)
    )


@router.get("/jobs", response_model=IngestionJobListResponse)
def list_ingestion_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionJobListResponse:
    result = service.list_jobs(limit=limit, offset=offset)
    return IngestionJobListResponse(
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        jobs=[IngestionJobResponse.model_validate(job) for job in result.jobs],
    )


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(
    job_id: str,
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionJobResponse:
    job = service.get_job(job_id)
    return IngestionJobResponse.model_validate(job)
