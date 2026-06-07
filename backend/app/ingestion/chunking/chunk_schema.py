"""
File: backend/app/ingestion/chunking/chunk_schema.py
Purpose: Defines the parent-child chunk schema consumed by embedding and retrieval.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import SupportedFileType
from app.ingestion.validators.block_validator import clean_required_text


class ParentChunk(BaseModel):
    """
    Larger structure-aware context unit.

    Parent chunks are loaded after child retrieval so the answer generator gets
    enough surrounding context without making vector search too noisy.
    """

    model_config = ConfigDict(use_enum_values=True)

    id: str
    document_id: str
    chunk_type: Literal["parent"] = "parent"
    parent_index: int = Field(ge=0)
    text: str
    token_count: int = Field(ge=1)
    source_block_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    parent_path: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "document_id", "text")
    @classmethod
    def clean_required_fields(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("parent_path", "source_block_ids", "source_refs")
    @classmethod
    def clean_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @model_validator(mode="after")
    def validate_source_blocks(self) -> "ParentChunk":
        if not self.source_block_ids:
            raise ValueError("parent chunk must reference at least one source block")
        return self


class ChildChunk(BaseModel):
    """
    Smaller searchable unit.

    Child chunks are the primary embedding targets. Each child points back to
    exactly one parent chunk for context expansion.
    """

    model_config = ConfigDict(use_enum_values=True)

    id: str
    document_id: str
    parent_chunk_id: str
    chunk_type: Literal["child"] = "child"
    child_index: int = Field(ge=0)
    text: str
    token_count: int = Field(ge=1)
    source_block_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    parent_path: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "document_id", "parent_chunk_id", "text")
    @classmethod
    def clean_required_fields(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("parent_path", "source_block_ids", "source_refs")
    @classmethod
    def clean_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @model_validator(mode="after")
    def validate_source_blocks(self) -> "ChildChunk":
        if not self.source_block_ids:
            raise ValueError("child chunk must reference at least one source block")
        return self


class ChunkedDocument(BaseModel):
    """
    Complete chunking result for one normalized document.
    """

    model_config = ConfigDict(use_enum_values=True)

    document_id: str
    title: str
    file_name: str
    file_type: SupportedFileType
    source_path: str | None = None
    parent_chunks: list[ParentChunk] = Field(default_factory=list)
    child_chunks: list[ChildChunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("document_id", "title", "file_name")
    @classmethod
    def clean_required_fields(cls, value: str) -> str:
        return clean_required_text(value)

    @model_validator(mode="after")
    def validate_chunks(self) -> "ChunkedDocument":
        if not self.parent_chunks:
            raise ValueError("chunked document must contain at least one parent chunk")

        if not self.child_chunks:
            raise ValueError("chunked document must contain at least one child chunk")

        parent_ids = {chunk.id for chunk in self.parent_chunks}
        for child in self.child_chunks:
            if child.parent_chunk_id not in parent_ids:
                raise ValueError("child chunk references an unknown parent chunk")

        return self
