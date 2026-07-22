"""
File: backend/app/integrations/database/transaction.py
Purpose: Provides a small transaction context helper for repositories.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any


@contextmanager
def transaction(connection: Any) -> Iterator[Any]:
    transaction_factory = getattr(connection, "transaction", None)
    context = transaction_factory() if callable(transaction_factory) else nullcontext()
    with context:
        yield connection
