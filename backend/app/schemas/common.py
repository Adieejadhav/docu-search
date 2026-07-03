"""
File: backend/app/schemas/common.py
Purpose: Defines API schema primitives shared across route groups.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
