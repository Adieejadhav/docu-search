from __future__ import annotations

import os
from pathlib import Path
import re
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
)

from app.api.dependencies import get_ingestion_job_service
from app.core.constants import MAX_FILE_SIZE_BYTES
from app.core.exceptions import IngestionError
from app.ingestion.jobs import IngestionJobService
from app.ingestion.parsers.factory import ParserFactory
from app.ingestion.validators.file_validator import validate_local_file
from app.schemas import (
    IngestionJobCreateResponse,
    IngestionJobListResponse,
    IngestionJobResponse,
)

router = APIRouter()

_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
DEFAULT_MAX_UPLOAD_FILES = 100


@router.post("/jobs", response_model=IngestionJobCreateResponse)
async def create_ingestion_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    clear_index: bool = Form(default=False),
    replace: bool = Form(default=True),
    continue_on_error: bool = Form(default=True),
    service: IngestionJobService = Depends(get_ingestion_job_service),
) -> IngestionJobCreateResponse:
    if not files:
        raise IngestionError("At least one file is required", code="NO_UPLOAD_FILES")

    max_upload_files = configured_int(
        "MAX_UPLOAD_FILES",
        DEFAULT_MAX_UPLOAD_FILES,
    )
    if len(files) > max_upload_files:
        raise IngestionError(
            "Too many files were uploaded",
            code="TOO_MANY_UPLOAD_FILES",
            details={
                "file_count": len(files),
                "max_upload_files": max_upload_files,
            },
        )

    upload_dir = service.upload_root / uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=True)
    source_paths: list[Path] = []
    supported_extensions = ParserFactory().supported_extensions
    max_file_size_bytes = configured_int(
        "MAX_UPLOAD_FILE_SIZE_BYTES",
        MAX_FILE_SIZE_BYTES,
    )

    for file_index, upload in enumerate(files, start=1):
        filename = sanitize_upload_filename(upload.filename or f"upload-{file_index}")
        suffix = Path(filename).suffix.lower()
        if suffix not in supported_extensions:
            raise IngestionError(
                "Uploaded file type is not supported",
                code="UNSUPPORTED_UPLOAD_FILE_TYPE",
                details={
                    "file_name": filename,
                    "supported_extensions": sorted(supported_extensions),
                },
            )

        destination = unique_destination(upload_dir, filename)
        await write_upload_file(
            upload,
            destination,
            max_file_size_bytes=max_file_size_bytes,
        )
        validate_local_file(
            destination,
            supported_extensions=set(supported_extensions),
            max_file_size_bytes=max_file_size_bytes,
            validate_content_type=True,
        )
        source_paths.append(destination)

    job = service.create_job(
        source_paths=source_paths,
        options={
            "recursive": False,
            "clear_index": clear_index,
            "replace": replace,
            "continue_on_error": continue_on_error,
        },
    )
    if ingestion_run_mode() == "background":
        background_tasks.add_task(service.run_job, job.id)
    return IngestionJobCreateResponse(job=IngestionJobResponse.model_validate(job))


@router.get("/jobs", response_model=IngestionJobListResponse)
def list_ingestion_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: IngestionJobService = Depends(get_ingestion_job_service),
) -> IngestionJobListResponse:
    result = service.store.list_jobs(limit=limit, offset=offset)
    return IngestionJobListResponse(
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        jobs=[IngestionJobResponse.model_validate(job) for job in result.jobs],
    )


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(
    job_id: str,
    service: IngestionJobService = Depends(get_ingestion_job_service),
) -> IngestionJobResponse:
    job = service.store.get_job(job_id)
    if job is None:
        raise IngestionError(
            "Ingestion job was not found",
            code="INGESTION_JOB_NOT_FOUND",
            details={"job_id": job_id},
        )
    return IngestionJobResponse.model_validate(job)


def sanitize_upload_filename(filename: str) -> str:
    raw_name = Path(filename).name.strip().replace(" ", "_")
    safe_name = _SAFE_FILENAME_PATTERN.sub("_", raw_name)
    if safe_name in {"", ".", ".."}:
        raise IngestionError(
            "Uploaded file name is invalid",
            code="INVALID_UPLOAD_FILENAME",
        )
    return safe_name


def unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate

    raise IngestionError(
        "Could not allocate a unique upload file name",
        code="UPLOAD_FILENAME_COLLISION",
        details={"file_name": filename},
    )


async def write_upload_file(
    upload: UploadFile,
    destination: Path,
    *,
    max_file_size_bytes: int,
) -> None:
    total_bytes = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_file_size_bytes:
                    raise IngestionError(
                        "Uploaded file is too large",
                        code="UPLOAD_FILE_TOO_LARGE",
                        details={
                            "file_name": upload.filename,
                            "max_file_size_bytes": max_file_size_bytes,
                        },
                    )
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def configured_int(env_name: str, default: int) -> int:
    raw_value = os.getenv(env_name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise IngestionError(
            "Integer environment setting is invalid",
            code="INVALID_INTEGER_ENV",
            details={"env_name": env_name, "value": raw_value},
        ) from exc


def ingestion_run_mode() -> str:
    mode = os.getenv("INGESTION_RUN_MODE", "background").strip().lower()
    if mode not in {"background", "worker"}:
        raise IngestionError(
            "INGESTION_RUN_MODE must be 'background' or 'worker'",
            code="INVALID_INGESTION_RUN_MODE",
            details={"INGESTION_RUN_MODE": mode},
        )
    return mode
