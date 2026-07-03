"""
File: backend/app/schemas/pipeline.py
Purpose: Defines ingestion pipeline test API schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PipelineNodeTestResponse(BaseModel):
    stage: Literal["validate", "parse", "chunk", "embed", "index"]
    status: Literal["completed"]
    duration_ms: float = Field(ge=0)
    summary: dict[str, Any] = Field(default_factory=dict)
    preview: list[dict[str, Any]] = Field(default_factory=list)
