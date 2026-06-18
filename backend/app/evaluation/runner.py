"""
File: backend/app/evaluation/runner.py
Purpose: Runs deterministic RAG retrieval and answer quality checks.
"""

from __future__ import annotations

import re
from statistics import fmean
from time import perf_counter
import unicodedata

from app.evaluation.dataset import BUILTIN_EVALUATION_CASES
from app.evaluation.schema import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationContext,
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationRunSummary,
)
from app.rag import RagAnswerer


class EvaluationRunner:
    """
    Executes built-in RAG checks against the configured index and answerer.
    """

    def __init__(self, *, index, answerer: RagAnswerer) -> None:
        self.index = index
        self.answerer = answerer

    def run(self, request: EvaluationRunRequest) -> EvaluationRunResponse:
        cases = self._selected_cases(request.case_ids)
        results = [self._run_case(case, request) for case in cases]
        return EvaluationRunResponse(
            top_k=request.top_k,
            include_answers=request.include_answers,
            summary=self._summary(results, include_answers=request.include_answers),
            cases=cases,
            results=results,
        )

    def _selected_cases(self, case_ids: list[str] | None) -> list[EvaluationCase]:
        if not case_ids:
            return list(BUILTIN_EVALUATION_CASES)

        case_by_id = {case.id: case for case in BUILTIN_EVALUATION_CASES}
        return [case_by_id[case_id] for case_id in case_ids if case_id in case_by_id]

    def _run_case(
        self,
        case: EvaluationCase,
        request: EvaluationRunRequest,
    ) -> EvaluationCaseResult:
        started = perf_counter()
        retrieval_started = perf_counter()
        retrieval_result = self.index.retrieve(case.question, top_k=request.top_k)
        retrieval_ms = duration_ms(retrieval_started)

        context_text = combined_context_text(retrieval_result)
        source_rank = first_source_rank(retrieval_result, case.expected_source_files)
        missing_context_terms = missing_terms(context_text, case.expected_context_terms)
        retrieval_passed = (
            not missing_context_terms
            and (not case.expected_source_files or source_rank is not None)
        )

        answer = None
        llm_model = None
        answer_ms = None
        citations: list[dict] = []
        missing_answer_terms: list[str] = []
        answer_passed: bool | None = None

        if request.include_answers:
            answer_started = perf_counter()
            rag_answer = self.answerer.answer(retrieval_result)
            answer_ms = duration_ms(answer_started)
            answer = rag_answer.answer
            llm_model = rag_answer.llm_model
            citations = rag_answer.citations
            missing_answer_terms = missing_terms(answer, case.expected_answer_terms)
            answer_passed = not missing_answer_terms

        passed = retrieval_passed and (answer_passed is not False)
        return EvaluationCaseResult(
            case_id=case.id,
            question=case.question,
            status="passed" if passed else "failed",
            retrieval_passed=retrieval_passed,
            answer_passed=answer_passed,
            source_rank=source_rank,
            missing_context_terms=missing_context_terms,
            missing_answer_terms=missing_answer_terms,
            answer=answer,
            llm_model=llm_model,
            retrieval_ms=retrieval_ms,
            answer_ms=answer_ms,
            total_ms=duration_ms(started),
            contexts=contexts_from_result(retrieval_result),
            citations=citations,
        )

    def _summary(
        self,
        results: list[EvaluationCaseResult],
        *,
        include_answers: bool,
    ) -> EvaluationRunSummary:
        total = len(results)
        passed = sum(1 for result in results if result.status == "passed")
        retrieval_passed = sum(1 for result in results if result.retrieval_passed)
        answer_passed = (
            sum(1 for result in results if result.answer_passed) if include_answers else None
        )
        return EvaluationRunSummary(
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            retrieval_passed_cases=retrieval_passed,
            answer_passed_cases=answer_passed,
            source_hit_rate=round(retrieval_passed / total, 4) if total else 0.0,
            answer_term_pass_rate=(
                round((answer_passed or 0) / total, 4) if include_answers and total else None
            ),
            mean_retrieval_ms=mean_ms([result.retrieval_ms for result in results]),
            mean_answer_ms=(
                mean_ms(
                    [
                        result.answer_ms
                        for result in results
                        if result.answer_ms is not None
                    ]
                )
                if include_answers
                else None
            ),
            mean_total_ms=mean_ms([result.total_ms for result in results]),
        )


def contexts_from_result(retrieval_result) -> list[EvaluationContext]:
    contexts: list[EvaluationContext] = []
    for item in retrieval_result.results:
        child = item.child_chunk
        parent = item.parent_chunk
        contexts.append(
            EvaluationContext(
                rank=item.rank,
                score=item.score,
                file_name=item.metadata.get("file_name"),
                source_refs=child.source_refs or parent.source_refs,
                parent_path=child.parent_path or parent.parent_path,
                text_excerpt=excerpt(parent.text),
            )
        )
    return contexts


def first_source_rank(retrieval_result, expected_files: list[str]) -> int | None:
    if not expected_files:
        return None

    expected = {file_name.lower() for file_name in expected_files}
    for item in retrieval_result.results:
        file_name = item.metadata.get("file_name")
        if isinstance(file_name, str) and file_name.lower() in expected:
            return item.rank
    return None


def combined_context_text(retrieval_result) -> str:
    parts: list[str] = []
    for item in retrieval_result.results:
        child = item.child_chunk
        parent = item.parent_chunk
        parts.extend(
            [
                str(item.metadata.get("file_name") or ""),
                " ".join(child.source_refs or parent.source_refs),
                " > ".join(child.parent_path or parent.parent_path),
                child.text,
                parent.text,
            ]
        )
    return "\n".join(parts)


def missing_terms(text: str | None, terms: list[str]) -> list[str]:
    normalized_text = normalize_for_match(text or "")
    return [
        term
        for term in terms
        if not term_matches(normalized_text=normalized_text, expected_term=term)
    ]


def term_matches(*, normalized_text: str, expected_term: str) -> bool:
    normalized_term = normalize_for_match(expected_term)
    if normalized_term in normalized_text:
        return True

    term_tokens = normalized_term.split()
    text_tokens = set(normalized_text.split())
    if len(term_tokens) <= 1:
        return False

    return all(token in text_tokens for token in term_tokens)


def normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.casefold())
    normalized = normalized.translate(
        str.maketrans(
            {
                "\u2010": "-",
                "\u2011": "-",
                "\u2012": "-",
                "\u2013": "-",
                "\u2014": "-",
                "\u2015": "-",
                "\u2212": "-",
                "\u00a0": " ",
                "\u202f": " ",
            }
        )
    )
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return " ".join(singularize_token(token) for token in tokens)


def singularize_token(token: str) -> str:
    if len(token) > 3 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def excerpt(text: str, *, limit: int = 520) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3].rstrip()}..."


def duration_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def mean_ms(values: list[float]) -> float:
    return round(fmean(values), 3) if values else 0.0
