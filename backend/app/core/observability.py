from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass(frozen=True)
class OperationMetricsSnapshot:
    total_count: int
    success_count: int
    failure_count: int
    success_by_operation: dict[str, int] = field(default_factory=dict)
    failure_by_operation: dict[str, int] = field(default_factory=dict)
    failure_by_code: dict[str, int] = field(default_factory=dict)
    total_duration_ms_by_operation: dict[str, float] = field(default_factory=dict)


class OperationMetricsRecorder:
    """
    Dependency-free in-process operation metrics recorder.

    This is intentionally generic so ingestion parsers, embedding jobs,
    retrieval, reranking, and API handlers can share the same primitive or swap
    it for a real metrics backend later.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._total_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._success_by_operation: dict[str, int] = {}
        self._failure_by_operation: dict[str, int] = {}
        self._failure_by_code: dict[str, int] = {}
        self._total_duration_ms_by_operation: dict[str, float] = {}

    def record_success(
        self,
        *,
        operation_name: str,
        duration_ms: float,
    ) -> None:
        with self._lock:
            self._total_count += 1
            self._success_count += 1
            self._success_by_operation[operation_name] = (
                self._success_by_operation.get(operation_name, 0) + 1
            )
            self._total_duration_ms_by_operation[operation_name] = (
                self._total_duration_ms_by_operation.get(operation_name, 0.0)
                + duration_ms
            )

    def record_failure(
        self,
        *,
        operation_name: str,
        error_code: str,
        duration_ms: float,
    ) -> None:
        with self._lock:
            self._total_count += 1
            self._failure_count += 1
            self._failure_by_operation[operation_name] = (
                self._failure_by_operation.get(operation_name, 0) + 1
            )
            self._failure_by_code[error_code] = (
                self._failure_by_code.get(error_code, 0) + 1
            )
            self._total_duration_ms_by_operation[operation_name] = (
                self._total_duration_ms_by_operation.get(operation_name, 0.0)
                + duration_ms
            )

    def snapshot(self) -> OperationMetricsSnapshot:
        with self._lock:
            return OperationMetricsSnapshot(
                total_count=self._total_count,
                success_count=self._success_count,
                failure_count=self._failure_count,
                success_by_operation=dict(self._success_by_operation),
                failure_by_operation=dict(self._failure_by_operation),
                failure_by_code=dict(self._failure_by_code),
                total_duration_ms_by_operation=dict(
                    self._total_duration_ms_by_operation
                ),
            )

    def reset(self) -> None:
        with self._lock:
            self._total_count = 0
            self._success_count = 0
            self._failure_count = 0
            self._success_by_operation.clear()
            self._failure_by_operation.clear()
            self._failure_by_code.clear()
            self._total_duration_ms_by_operation.clear()


DEFAULT_OPERATION_METRICS_RECORDER = OperationMetricsRecorder()
