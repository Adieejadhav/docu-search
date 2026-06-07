"""
File: backend/app/ingestion/validators/file_validator.py
Purpose: Validates local/uploaded files before they enter the ingestion parser layer.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.constants import (
    CONTENT_SNIFF_SAMPLE_SIZE_BYTES,
    DEFAULT_TEXT_ENCODINGS,
    EXPECTED_CONTENT_TYPES_BY_EXTENSION,
    IGNORED_INGESTION_FILE_PREFIXES,
    MAX_FILE_SIZE_BYTES,
    MEDIA_TYPE_BY_CONTENT_TYPE,
    SUPPORTED_INGESTION_EXTENSIONS,
)
from app.core.exceptions import FileValidationError


@dataclass(frozen=True)
class DetectedContentType:
    content_type: str
    media_type: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ValidatedFile:
    file_path: Path
    file_name: str
    extension: str
    size_bytes: int
    detected_content_type: str
    media_type: str


def should_skip_ingestion_file(file_path: str | Path) -> bool:
    path = Path(file_path)
    return path.name.startswith(IGNORED_INGESTION_FILE_PREFIXES)


def validate_local_file(
    file_path: str | Path,
    supported_extensions: set[str] | None = None,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    validate_content_type: bool = True,
) -> ValidatedFile:
    """
    Validate a local file before parsing.

    Validation includes path checks, extension allow-listing, size limits, and
    content sniffing so renamed files are rejected before parser execution.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileValidationError(
            f"File does not exist: {path}",
            code="FILE_NOT_FOUND",
            details={"file_path": str(path)},
        )

    if not path.is_file():
        raise FileValidationError(
            f"Path is not a file: {path}",
            code="INVALID_FILE_PATH",
            details={"file_path": str(path)},
        )

    extension = path.suffix.lower()
    allowed_extensions = _normalize_extensions(
        SUPPORTED_INGESTION_EXTENSIONS
        if supported_extensions is None
        else supported_extensions
    )

    if extension not in allowed_extensions:
        raise FileValidationError(
            f"Unsupported file type: {extension}",
            code="UNSUPPORTED_FILE_TYPE",
            details={
                "extension": extension,
                "supported_extensions": sorted(allowed_extensions),
            },
        )

    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        raise FileValidationError(
            f"Unable to read file metadata: {path}",
            code="FILE_STAT_FAILED",
            details={"file_path": str(path)},
        ) from exc

    if size_bytes == 0:
        raise FileValidationError(
            "File is empty",
            code="EMPTY_FILE",
            details={"file_path": str(path)},
        )

    if size_bytes > max_file_size_bytes:
        raise FileValidationError(
            "File is too large",
            code="FILE_TOO_LARGE",
            details={
                "file_path": str(path),
                "size_bytes": size_bytes,
                "max_file_size_bytes": max_file_size_bytes,
            },
        )

    detected_content_type = DetectedContentType(
        content_type="not_checked",
        media_type="application/octet-stream",
        details={},
    )
    if validate_content_type:
        detected_content_type = detect_content_type(path, extension)
        _validate_detected_content_type(
            extension=extension,
            detected_content_type=detected_content_type,
            file_path=path,
        )

    return ValidatedFile(
        file_path=path,
        file_name=path.name,
        extension=extension,
        size_bytes=size_bytes,
        detected_content_type=detected_content_type.content_type,
        media_type=detected_content_type.media_type,
    )


def detect_content_type(path: Path, extension: str | None = None) -> DetectedContentType:
    normalized_extension = (extension or path.suffix).lower()
    sample = _read_sample(path)

    if sample.startswith(b"%PDF-"):
        return _detected("pdf", signature="%PDF-")

    if zipfile.is_zipfile(path):
        return _detect_zip_container(path)

    if _looks_like_binary(sample):
        return _detected("binary", reason="binary_sample")

    text = _decode_text(path)
    if normalized_extension == ".json":
        return _detect_json_content(text)

    if normalized_extension == ".csv":
        return _detected("csv", encoding="text")

    if normalized_extension in {".md", ".markdown"}:
        return _detected("markdown", encoding="text")

    return _detected("text", encoding="text")


def _validate_detected_content_type(
    *,
    extension: str,
    detected_content_type: DetectedContentType,
    file_path: Path,
) -> None:
    expected_content_types = EXPECTED_CONTENT_TYPES_BY_EXTENSION.get(extension)
    if expected_content_types is None:
        return

    if detected_content_type.content_type in expected_content_types:
        return

    raise FileValidationError(
        "File content does not match the declared extension",
        code="FILE_CONTENT_TYPE_MISMATCH",
        details={
            "file_path": str(file_path),
            "extension": extension,
            "expected_content_types": sorted(expected_content_types),
            "detected_content_type": detected_content_type.content_type,
            "detected_media_type": detected_content_type.media_type,
            **detected_content_type.details,
        },
    )


def _normalize_extensions(extensions: set[str]) -> set[str]:
    return {
        extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for extension in extensions
    }


def _read_sample(path: Path) -> bytes:
    try:
        with path.open("rb") as file:
            return file.read(CONTENT_SNIFF_SAMPLE_SIZE_BYTES)
    except OSError as exc:
        raise FileValidationError(
            f"Unable to read file content: {path}",
            code="FILE_READ_FAILED",
            details={"file_path": str(path)},
        ) from exc


def _decode_text(path: Path) -> str:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise FileValidationError(
            f"Unable to read file content: {path}",
            code="FILE_READ_FAILED",
            details={"file_path": str(path)},
        ) from exc

    for encoding in DEFAULT_TEXT_ENCODINGS:
        try:
            return content.decode(encoding).lstrip("\ufeff")
        except UnicodeDecodeError:
            continue

    raise FileValidationError(
        "Unable to decode text file during content validation",
        code="FILE_TEXT_DECODE_FAILED",
        details={
            "file_path": str(path),
            "encodings": DEFAULT_TEXT_ENCODINGS,
        },
    )


def _looks_like_binary(sample: bytes) -> bool:
    if not sample:
        return False

    if b"\x00" in sample:
        return True

    allowed_control_bytes = {7, 8, 9, 10, 12, 13, 27}
    suspicious_bytes = 0

    for byte in sample:
        if byte >= 32 or byte in allowed_control_bytes:
            continue
        suspicious_bytes += 1

    return suspicious_bytes / len(sample) > 0.30


def _detect_zip_container(path: Path) -> DetectedContentType:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise FileValidationError(
            "Unable to inspect ZIP-based document content",
            code="ZIP_INSPECTION_FAILED",
            details={"file_path": str(path)},
        ) from exc

    if "[Content_Types].xml" in names and "word/document.xml" in names:
        return _detected("docx", container="zip")

    if "[Content_Types].xml" in names and "ppt/presentation.xml" in names:
        return _detected("pptx", container="zip")

    if "[Content_Types].xml" in names and "xl/workbook.xml" in names:
        return _detected("xlsx", container="zip")

    return _detected("zip", container="zip")


def _detect_json_content(text: str) -> DetectedContentType:
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return _detected(
            "text",
            invalid_json=True,
            line=exc.lineno,
            column=exc.colno,
            reason=exc.msg,
        )

    return _detected("json", encoding="text")


def _detected(content_type: str, **details: Any) -> DetectedContentType:
    return DetectedContentType(
        content_type=content_type,
        media_type=MEDIA_TYPE_BY_CONTENT_TYPE.get(
            content_type,
            MEDIA_TYPE_BY_CONTENT_TYPE["unknown"],
        ),
        details=details,
    )
