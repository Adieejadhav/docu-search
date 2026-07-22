"""
File: backend/app/lifespan.py
Purpose: FastAPI lifespan setup for shared application dependencies.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap import get_application_container
from app.bootstrap.startup_checks import run_startup_checks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = get_application_container()
    app.state.container = container
    app.state.startup_checks = run_startup_checks(container.settings)
    try:
        yield
    finally:
        container.close()
