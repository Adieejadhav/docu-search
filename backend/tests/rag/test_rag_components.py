from __future__ import annotations

from app.ingestion.chunking import ChildChunk, ParentChunk
from app.rag import CitationValidator, RagContextBuilder, RagPromptBuilder
from app.rag.retrieval import RetrievedChunk, RetrievalResult


def test_rag_components_preserve_prompt_context_and_citation_shapes():
    retrieval = _retrieval_result()

    context = RagContextBuilder().build(retrieval)
    messages = RagPromptBuilder().build_messages(
        query=retrieval.query,
        context=context,
    )
    citations = CitationValidator().citations(retrieval)

    assert "[1] score=0.9100 file=policy.md source=lines:24-30 path=Policy" in context
    assert messages[0]["role"] == "system"
    assert messages[1]["content"].startswith("Question:\nWhich policy?")
    assert citations == [
        {
            "rank": 1,
            "score": 0.91,
            "file_name": "policy.md",
            "file_type": "md",
            "source_refs": ["lines:24-30"],
            "parent_path": ["Policy"],
            "child_chunk_id": "child-1",
            "parent_chunk_id": "parent-1",
        }
    ]


def _retrieval_result() -> RetrievalResult:
    parent = ParentChunk(
        id="parent-1",
        document_id="doc-1",
        parent_index=0,
        text="P-004 covers satellite mode.",
        token_count=5,
        source_block_ids=["block-1"],
        source_refs=["lines:24-30"],
        parent_path=["Policy"],
    )
    child = ChildChunk(
        id="child-1",
        document_id="doc-1",
        parent_chunk_id="parent-1",
        child_index=0,
        text="Satellite mode exception.",
        token_count=3,
        source_block_ids=["block-1"],
        source_refs=["lines:24-30"],
        parent_path=["Policy"],
    )
    return RetrievalResult(
        query="Which policy?",
        embedding_model="fake-embedding",
        top_k=1,
        results=[
            RetrievedChunk(
                rank=1,
                score=0.91,
                child_chunk=child,
                parent_chunk=parent,
                metadata={"file_name": "policy.md", "file_type": "md"},
            )
        ],
    )
