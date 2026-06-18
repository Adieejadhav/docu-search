from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_chunk_index,
    get_evaluation_history_store,
    get_rag_answerer,
)
from app.core.exceptions import RetrievalError
from app.evaluation import (
    BUILTIN_EVALUATION_CASES,
    EvaluationHistoryStore,
    EvaluationCase,
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationRunRecord,
    EvaluationRunner,
)
from app.indexing import PgVectorChunkIndex
from app.rag import RagAnswerer
from app.schemas import (
    EvaluationRunHistoryResponse,
    EvaluationRunRecordDetail,
    EvaluationRunRecordSummary,
)

router = APIRouter()


@router.get("/cases", response_model=list[EvaluationCase])
def list_evaluation_cases() -> list[EvaluationCase]:
    return list(BUILTIN_EVALUATION_CASES)


@router.post("/run", response_model=EvaluationRunResponse)
def run_evaluation(
    request: EvaluationRunRequest,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    answerer: RagAnswerer = Depends(get_rag_answerer),
    history_store: EvaluationHistoryStore = Depends(get_evaluation_history_store),
) -> EvaluationRunResponse:
    response = EvaluationRunner(index=index, answerer=answerer).run(request)
    history_store.record_run(request=request, response=response)
    return response


@router.get("/runs", response_model=EvaluationRunHistoryResponse)
def list_evaluation_runs(
    limit: int = 20,
    offset: int = 0,
    history_store: EvaluationHistoryStore = Depends(get_evaluation_history_store),
) -> EvaluationRunHistoryResponse:
    run_list = history_store.list_runs(limit=limit, offset=offset)
    return EvaluationRunHistoryResponse(
        total=run_list.total,
        limit=run_list.limit,
        offset=run_list.offset,
        runs=[run_summary(run) for run in run_list.runs],
    )


@router.get("/runs/{run_id}", response_model=EvaluationRunRecordDetail)
def get_evaluation_run(
    run_id: str,
    history_store: EvaluationHistoryStore = Depends(get_evaluation_history_store),
) -> EvaluationRunRecordDetail:
    run = history_store.get_run(run_id)
    if run is None:
        raise RetrievalError(
            "Evaluation run was not found",
            code="EVALUATION_RUN_NOT_FOUND",
            details={"run_id": run_id},
        )

    return run_detail(run)


def run_summary(run: EvaluationRunRecord) -> EvaluationRunRecordSummary:
    return EvaluationRunRecordSummary(
        id=run.id,
        top_k=run.top_k,
        include_answers=run.include_answers,
        total_cases=run.total_cases,
        passed_cases=run.passed_cases,
        failed_cases=run.failed_cases,
        source_hit_rate=run.source_hit_rate,
        answer_term_pass_rate=run.answer_term_pass_rate,
        mean_total_ms=run.mean_total_ms,
        created_at=run.created_at,
    )


def run_detail(run: EvaluationRunRecord) -> EvaluationRunRecordDetail:
    return EvaluationRunRecordDetail(
        **run_summary(run).model_dump(),
        response=run.response,
    )
