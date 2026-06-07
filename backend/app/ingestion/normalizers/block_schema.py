"""
File: backend/app/ingestion/normalizers/block_schema.py
Purpose: Defines the common normalized document schema returned by every parser.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import BlockType, SupportedFileType
from app.ingestion.validators.block_validator import (
    clean_optional_text,
    clean_required_text,
    strip_text,
    validate_document_block_rules,
    validate_number_range,
)


class SourceLocation(BaseModel):
    """
    Location of a block inside the original source document.

    Not every parser will fill every field.

    Examples:
    - PDF: page_number
    - Markdown/TXT: line_start, line_end
    - PPTX: slide_number
    - XLSX/CSV: sheet_name, row_start, row_end
    """

    page_number: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    slide_number: int | None = Field(default=None, ge=1)
    sheet_name: str | None = None
    row_start: int | None = Field(default=None, ge=1)
    row_end: int | None = Field(default=None, ge=1)

    @field_validator("sheet_name")
    @classmethod
    def clean_sheet_name(cls, value: str | None) -> str | None:
        return clean_optional_text(value)

    @model_validator(mode="after")
    def validate_ranges(self) -> "SourceLocation":
        validate_number_range(
            start=self.line_start,
            end=self.line_end,
            start_name="line_start",
            end_name="line_end",
        )

        validate_number_range(
            start=self.row_start,
            end=self.row_end,
            start_name="row_start",
            end_name="row_end",
        )

        return self


class DocumentBlock(BaseModel):
    """
    Normalized block returned by every parser.

    This is the common internal structure used before chunking.
    """

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    block_type: BlockType
    text: str = ""
    order: int = Field(ge=0)

    # Used only for heading blocks.
    level: int | None = Field(default=None, ge=1, le=6)

    # Example:
    # ["Employee Handbook", "Leave Policy", "Annual Leave"]
    parent_path: list[str] = Field(default_factory=list)

    source_location: SourceLocation = Field(default_factory=SourceLocation)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return strip_text(value)

    @field_validator("parent_path")
    @classmethod
    def clean_parent_path(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @model_validator(mode="after")
    def validate_block(self) -> "DocumentBlock":
        validate_document_block_rules(
            block_type=self.block_type,
            text=self.text,
            level=self.level,
        )
        return self


class ParsedDocument(BaseModel):
    """
    Final parser output.

    Every parser must return this object.
    """

    model_config = ConfigDict(use_enum_values=True)

    title: str
    file_name: str
    file_type: SupportedFileType
    source_path: str | None = None
    blocks: list[DocumentBlock] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return clean_required_text(value, field_name="title")

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, value: str) -> str:
        return clean_required_text(value, field_name="file_name")

    @field_validator("source_path")
    @classmethod
    def clean_source_path(cls, value: str | None) -> str | None:
        return clean_optional_text(value)

    @model_validator(mode="after")
    def validate_document(self) -> "ParsedDocument":
        if not self.blocks:
            raise ValueError("parsed document must contain at least one block")

        return self
