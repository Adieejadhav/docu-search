"""
File: backend/app/search/retrieval/retrieval_schema.py
Purpose: Defines retrieval results returned by the parent-child retriever.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ingestion.chunking import ChildChunk, ParentChunk
from app.ingestion.validators.block_validator import clean_required_text


class RetrievedChunk(BaseModel):
    """
    One ranked child match plus its expanded parent context.
    """

    model_config = ConfigDict(use_enum_values=True)

    rank: int = Field(ge=1)
    score: float
    child_chunk: ChildChunk
    parent_chunk: ParentChunk
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """
    Complete retrieval response for one query.
    """

    model_config = ConfigDict(use_enum_values=True)

    query: str
    embedding_model: str
    top_k: int = Field(ge=1)
    results: list[RetrievedChunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query", "embedding_model")
    @classmethod
    def clean_required_fields(cls, value: str) -> str:
        return clean_required_text(value)
