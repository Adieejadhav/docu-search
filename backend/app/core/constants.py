"""
File: backend/app/core/constants.py
Purpose: Stores shared application constants and enums used across backend modules.
"""

from __future__ import annotations

from enum import Enum


class BlockType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE = "code"
    JSON = "json"
    PAGE_BREAK = "page_break"
    UNKNOWN = "unknown"


class SupportedFileType(str, Enum):
    TXT = "txt"
    MARKDOWN = "md"
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"


SUPPORTED_TEXT_EXTENSIONS = {".txt"}

SUPPORTED_MARKDOWN_EXTENSIONS = {
    ".md",
    ".markdown",
}

SUPPORTED_PDF_EXTENSIONS = {".pdf"}

SUPPORTED_DOCX_EXTENSIONS = {".docx"}

SUPPORTED_PPTX_EXTENSIONS = {".pptx"}

SUPPORTED_XLSX_EXTENSIONS = {".xlsx"}

SUPPORTED_CSV_EXTENSIONS = {".csv"}

SUPPORTED_JSON_EXTENSIONS = {".json"}

SUPPORTED_INGESTION_EXTENSIONS = {
    *SUPPORTED_TEXT_EXTENSIONS,
    *SUPPORTED_MARKDOWN_EXTENSIONS,
    *SUPPORTED_PDF_EXTENSIONS,
    *SUPPORTED_DOCX_EXTENSIONS,
    *SUPPORTED_PPTX_EXTENSIONS,
    *SUPPORTED_XLSX_EXTENSIONS,
    *SUPPORTED_CSV_EXTENSIONS,
    *SUPPORTED_JSON_EXTENSIONS,
}

# Backward-compatible alias for early ingestion code that imported this name.
SUPPORTED_V0_EXTENSIONS = SUPPORTED_INGESTION_EXTENSIONS

IGNORED_INGESTION_FILE_PREFIXES = ("~$",)

NORMALIZED_DOCUMENT_SCHEMA_VERSION = "1.0"

DEFAULT_TEXT_ENCODINGS = [
    "utf-8",
    "utf-8-sig",
    "cp1252",
    "latin-1",
]

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

CONTENT_SNIFF_SAMPLE_SIZE_BYTES = 8192

TEXT_COMPATIBLE_CONTENT_TYPES = frozenset(
    {
        "text",
        "markdown",
        "csv",
        "json",
    }
)

EXPECTED_CONTENT_TYPES_BY_EXTENSION = {
    ".txt": TEXT_COMPATIBLE_CONTENT_TYPES,
    ".md": TEXT_COMPATIBLE_CONTENT_TYPES,
    ".markdown": TEXT_COMPATIBLE_CONTENT_TYPES,
    ".csv": frozenset({"text", "csv"}),
    ".json": frozenset({"json"}),
    ".pdf": frozenset({"pdf"}),
    ".docx": frozenset({"docx"}),
    ".pptx": frozenset({"pptx"}),
    ".xlsx": frozenset({"xlsx"}),
}

MEDIA_TYPE_BY_CONTENT_TYPE = {
    "text": "text/plain",
    "markdown": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
    "binary": "application/octet-stream",
    "unknown": "application/octet-stream",
}

MIN_HEADING_LEVEL = 1
MAX_HEADING_LEVEL = 6
