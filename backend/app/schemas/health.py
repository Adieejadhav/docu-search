"""
File: backend/app/schemas/health.py
Purpose: Defines health-check API response schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthServiceStatus(BaseModel):
    status: Literal["ok", "degraded"]
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    database: HealthServiceStatus
    embedding: HealthServiceStatus
    llm: HealthServiceStatus
