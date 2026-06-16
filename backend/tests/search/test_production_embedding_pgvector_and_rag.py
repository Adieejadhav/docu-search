from __future__ import annotations

import pytest

from app.core.exceptions import EmbeddingError, RetrievalError
from app.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.indexing import PgVectorChunkIndex
from app.ingestion.chunking import ChildChunk, ChunkedDocument, ParentChunk
from app.llm import OllamaChatClient
from app.rag import RagAnswerer
from app.search.retrieval import RetrievedChunk, RetrievalResult


def test_local_embedding_provider_uses_model_client_and_validates_dimensions():
    model_client = _FakeSentenceTransformerModel(
        vectors=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )
    provider = LocalSentenceTransformerEmbeddingProvider(
        model="BAAI/bge-small-en-v1.5",
        dimensions=3,
        batch_size=2,
        model_client=model_client,
    )

    vectors = provider.embed_texts(["first text", "second text"])

    assert provider.name == "local-sentence-transformers-BAAI/bge-small-en-v1.5-3d"
    assert vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert model_client.calls[0]["texts"] == ["first text", "second text"]
    assert model_client.calls[0]["batch_size"] == 2
    assert model_client.calls[0]["normalize_embeddings"] is True


def test_local_embedding_provider_rejects_empty_text():
    provider = LocalSentenceTransformerEmbeddingProvider(
        dimensions=3,
        model_client=_FakeSentenceTransformerModel(vectors=[]),
    )

    with pytest.raises(EmbeddingError) as error:
        provider.embed_texts(["  "])

    assert error.value.code == "EMPTY_EMBEDDING_TEXT"


def test_pgvector_index_requires_database_url(monkeypatch):
    monkeypatch.setenv("DOCU_SEARCH_SKIP_DOTENV", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RetrievalError) as error:
        PgVectorChunkIndex(embedding_provider=_FakeEmbeddingProvider())

    assert error.value.code == "DATABASE_URL_MISSING"


def test_ollama_chat_client_uses_configured_client():
    client = _FakeOllamaClient(answer="Grounded answer [1].")
    llm = OllamaChatClient(
        model="gpt-oss:120b-cloud",
        host="http://localhost:11434",
        client=client,
    )

    answer = llm.generate(
        [
            {"role": "system", "content": "Use context."},
            {"role": "user", "content": "Question?"},
        ]
    )

    assert answer == "Grounded answer [1]."
    assert client.calls[0]["model"] == "gpt-oss:120b-cloud"
    assert client.calls[0]["stream"] is False


def test_rag_answerer_builds_grounded_answer_with_citations():
    retrieval_result = _retrieval_result()
    llm_client = OllamaChatClient(
        client=_FakeOllamaClient(answer="Use policy P-004 for the 14-day exception [1].")
    )

    answer = RagAnswerer(llm_client=llm_client).answer(retrieval_result)

    assert answer.answer == "Use policy P-004 for the 14-day exception [1]."
    assert answer.llm_model == "ollama-gpt-oss:120b-cloud"
    assert answer.citations[0]["file_name"] == "policy.md"
    assert answer.citations[0]["source_refs"] == ["lines:24-30"]


class _FakeSentenceTransformerModel:
    def __init__(self, *, vectors: list[list[float]]) -> None:
        self._vectors = vectors
        self.calls: list[dict[str, object]] = []

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> list[list[float]]:
        self.calls.append(
            {
                "texts": texts,
                "batch_size": batch_size,
                "convert_to_numpy": convert_to_numpy,
                "normalize_embeddings": normalize_embeddings,
                "show_progress_bar": show_progress_bar,
            }
        )
        return self._vectors[: len(texts)]


class _FakeEmbeddingProvider:
    name = "fake-production-test"
    dimensions = 3

    def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class _FakeOllamaClient:
    def __init__(self, *, answer: str) -> None:
        self._answer = answer
        self.calls: list[dict[str, object]] = []

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        options: dict[str, float],
        stream: bool,
    ) -> dict[str, dict[str, str]]:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "options": options,
                "stream": stream,
            }
        )
        return {"message": {"content": self._answer}}


def _retrieval_result() -> RetrievalResult:
    parent_chunk = ParentChunk(
        id="parent-1",
        document_id="doc-1",
        parent_index=0,
        text=(
            "P-004 password rotation exception: offline substations in satellite "
            "mode rotate at the next successful sync within 14 days."
        ),
        token_count=20,
        source_block_ids=["block-1"],
        source_refs=["lines:24-30"],
        parent_path=["Policy Table"],
        metadata={},
    )
    child_chunk = ChildChunk(
        id="child-1",
        document_id="doc-1",
        parent_chunk_id="parent-1",
        child_index=0,
        text="P-004 includes the 14-day satellite-mode exception.",
        token_count=9,
        source_block_ids=["block-1"],
        source_refs=["lines:24-30"],
        parent_path=["Policy Table"],
        metadata={},
    )
    chunked_document = ChunkedDocument(
        document_id="doc-1",
        title="Policy",
        file_name="policy.md",
        file_type="md",
        source_path="policy.md",
        parent_chunks=[parent_chunk],
        child_chunks=[child_chunk],
        metadata={},
    )
    assert chunked_document.parent_chunks[0].id == "parent-1"
    return RetrievalResult(
        query="Which policy mentions the 14-day satellite-mode exception?",
        embedding_model="local-sentence-transformers-BAAI/bge-small-en-v1.5-384d",
        top_k=1,
        results=[
            RetrievedChunk(
                rank=1,
                score=0.91,
                child_chunk=child_chunk,
                parent_chunk=parent_chunk,
                metadata={"file_name": "policy.md", "file_type": "md"},
            )
        ],
        metadata={},
    )
