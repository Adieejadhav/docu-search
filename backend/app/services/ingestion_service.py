from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Protocol
from uuid import uuid4

from app.core.config import IngestionSettings, get_settings
from app.core.exceptions import IngestionError
from app.ingestion.jobs import (
    IngestionJobList,
    IngestionJobRecord,
    IngestionJobService,
)
from app.ingestion.parsers.factory import ParserFactory
from app.ingestion.validators.file_validator import (
    should_skip_ingestion_file,
    validate_local_file,
)

_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_UPLOAD_PATH_SEPARATOR_PATTERN = re.compile(r"[\\/]+")


class UploadFileSource(Protocol):
    filename: str | None

    async def read(self, size: int = -1) -> bytes:
        ...

    async def close(self) -> None:
        ...


@dataclass(frozen=True)
class IngestionUploadOptions:
    clear_index: bool
    replace: bool
    continue_on_error: bool


@dataclass(frozen=True)
class IngestionJobPlan:
    job: IngestionJobRecord
    run_in_background: bool


class IngestionService:
    """
    Coordinates API-facing ingestion actions without depending on FastAPI.
    """

    def __init__(
        self,
        *,
        job_service: IngestionJobService,
        settings: IngestionSettings | None = None,
        parser_factory: ParserFactory | None = None,
    ) -> None:
        self.job_service = job_service
        self.settings = settings or get_settings().ingestion
        self.parser_factory = parser_factory or ParserFactory()

    async def create_upload_job(
        self,
        *,
        files: list[UploadFileSource],
        options: IngestionUploadOptions,
    ) -> IngestionJobPlan:
        if not files:
            raise IngestionError("At least one file is required", code="NO_UPLOAD_FILES")

        max_upload_files = self.settings.max_upload_files
        if len(files) > max_upload_files:
            raise IngestionError(
                "Too many files were uploaded",
                code="TOO_MANY_UPLOAD_FILES",
                details={
                    "file_count": len(files),
                    "max_upload_files": max_upload_files,
                },
            )

        upload_dir = self.job_service.upload_root / uuid4().hex
        upload_dir.mkdir(parents=True, exist_ok=True)
        source_paths: list[Path] = []
        supported_extensions = self.parser_factory.supported_extensions
        max_file_size_bytes = self.settings.max_upload_file_size_bytes

        for file_index, upload in enumerate(files, start=1):
            raw_filename = upload.filename or f"upload-{file_index}"
            if should_skip_upload_file(raw_filename):
                await upload.close()
                continue

            try:
                upload_path = sanitize_upload_relative_path(raw_filename)
            except IngestionError:
                await upload.close()
                raise
            suffix = upload_path.suffix.lower()
            if suffix not in supported_extensions:
                await upload.close()
                raise IngestionError(
                    "Uploaded file type is not supported",
                    code="UNSUPPORTED_UPLOAD_FILE_TYPE",
                    details={
                        "file_name": str(upload_path),
                        "supported_extensions": sorted(supported_extensions),
                    },
                )

            destination = unique_destination(upload_dir, upload_path)
            await write_upload_file(
                upload,
                destination,
                max_file_size_bytes=max_file_size_bytes,
            )
            if should_skip_ingestion_file(destination):
                destination.unlink(missing_ok=True)
                continue
            validate_local_file(
                destination,
                supported_extensions=set(supported_extensions),
                max_file_size_bytes=max_file_size_bytes,
                validate_content_type=True,
            )
            source_paths.append(destination)

        if not source_paths:
            raise IngestionError(
                "No readable documents were found in the upload",
                code="NO_READABLE_UPLOAD_FILES",
            )

        job = self.job_service.create_job(
            source_paths=source_paths,
            options={
                "recursive": False,
                "clear_index": options.clear_index,
                "replace": options.replace,
                "continue_on_error": options.continue_on_error,
            },
        )
        return IngestionJobPlan(
            job=job,
            run_in_background=self._ingestion_run_mode() == "background",
        )

    def list_jobs(self, *, limit: int, offset: int) -> IngestionJobList:
        return self.job_service.store.list_jobs(limit=limit, offset=offset)

    def get_job(self, job_id: str) -> IngestionJobRecord:
        job = self.job_service.store.get_job(job_id)
        if job is None:
            raise IngestionError(
                "Ingestion job was not found",
                code="INGESTION_JOB_NOT_FOUND",
                details={"job_id": job_id},
            )
        return job

    def run_job(self, job_id: str) -> None:
        self.job_service.run_job(job_id)

    def _ingestion_run_mode(self) -> str:
        mode = self.settings.run_mode.strip().lower()
        if mode not in {"background", "worker"}:
            raise IngestionError(
                "INGESTION_RUN_MODE must be 'background' or 'worker'",
                code="INVALID_INGESTION_RUN_MODE",
                details={"INGESTION_RUN_MODE": mode},
            )
        return mode


def sanitize_upload_filename(filename: str) -> str:
    raw_name = _UPLOAD_PATH_SEPARATOR_PATTERN.split(filename.strip())[-1].replace(
        " ",
        "_",
    )
    safe_name = _SAFE_FILENAME_PATTERN.sub("_", raw_name)
    if safe_name in {"", ".", ".."}:
        raise IngestionError(
            "Uploaded file name is invalid",
            code="INVALID_UPLOAD_FILENAME",
        )
    return safe_name


def sanitize_upload_relative_path(filename: str) -> Path:
    raw_parts = _UPLOAD_PATH_SEPARATOR_PATTERN.split(filename.strip())
    safe_parts: list[str] = []

    for raw_part in raw_parts:
        cleaned_part = raw_part.strip().replace(" ", "_")
        if cleaned_part in {"", "."}:
            continue
        if cleaned_part == "..":
            raise IngestionError(
                "Uploaded file name is invalid",
                code="INVALID_UPLOAD_FILENAME",
            )

        safe_part = _SAFE_FILENAME_PATTERN.sub("_", cleaned_part)
        if safe_part in {"", ".", ".."}:
            raise IngestionError(
                "Uploaded file name is invalid",
                code="INVALID_UPLOAD_FILENAME",
            )
        safe_parts.append(safe_part)

    if not safe_parts:
        raise IngestionError(
            "Uploaded file name is invalid",
            code="INVALID_UPLOAD_FILENAME",
        )

    return Path(*safe_parts)


def should_skip_upload_file(filename: str) -> bool:
    base_name = _UPLOAD_PATH_SEPARATOR_PATTERN.split(filename.strip())[-1]
    return should_skip_ingestion_file(base_name)


def unique_destination(directory: Path, filename: str | Path) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    parent = candidate.parent
    for index in range(2, 1000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate

    raise IngestionError(
        "Could not allocate a unique upload file name",
        code="UPLOAD_FILENAME_COLLISION",
        details={"file_name": str(filename)},
    )


async def write_upload_file(
    upload: UploadFileSource,
    destination: Path,
    *,
    max_file_size_bytes: int,
) -> None:
    total_bytes = 0
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
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
