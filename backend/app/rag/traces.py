"""
File: backend/app/rag/traces.py
Purpose: Compatibility exports for RAG trace records and persistence.

Trace persistence now lives in app.repositories.trace_repository. This module
keeps the previous import path stable for services, tests, and scripts.
"""

from __future__ import annotations

from app.repositories.trace_repository import (
    RagTraceList,
    RagTraceRecord,
    RagTraceStore,
    TraceRepository,
)

__all__ = [
    "RagTraceList",
    "RagTraceRecord",
    "RagTraceStore",
    "TraceRepository",
]
