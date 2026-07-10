"""
File: backend/app/lifespan.py
Purpose: FastAPI lifespan setup for shared application dependencies.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap import get_application_container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.container = get_application_container()
    yield
