from __future__ import annotations

import json

from app.core.constants import BlockType, SupportedFileType
from app.ingestion.cli.chunk_documents import main
from app.ingestion.normalizers import DocumentNormalizer
from app.ingestion.normalizers.block_schema import (
    DocumentBlock,
    ParsedDocument,
    SourceLocation,
)


def test_chunk_documents_cli_writes_chunk_json_for_single_document(tmp_path):
    input_file = tmp_path / "fixture.normalized.json"
    output_file = tmp_path / "fixture.chunks.json"
    document = _normalized_document()
    input_file.write_text(
        json.dumps(document.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(input_file),
            "--output-json",
            str(output_file),
            "--parent-target-tokens",
            "80",
            "--parent-hard-max-tokens",
            "120",
            "--child-target-tokens",
            "40",
            "--child-overlap-tokens",
            "0",
            "--max-children",
            "1",
        ]
    )

    payload = json.loads(output_file.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["file_name"] == "fixture.md"
    assert payload["metadata"]["chunking_strategy"] == "structure_aware_parent_child"
    assert payload["metadata"]["child_target_tokens"] == 40
    assert len(payload["parent_chunks"]) >= 1
    assert len(payload["child_chunks"]) >= 1
    assert payload["child_chunks"][0]["parent_chunk_id"] in {
        parent["id"] for parent in payload["parent_chunks"]
    }
    assert any(
        "lines:5-7" in child["source_refs"] for child in payload["child_chunks"]
    )


def test_chunk_documents_cli_writes_chunk_json_for_document_list(tmp_path):
    input_file = tmp_path / "fixtures.normalized.json"
    output_file = tmp_path / "fixtures.chunks.json"
    documents = [_normalized_document(file_name="one.md"), _normalized_document(file_name="two.md")]
    input_file.write_text(
        json.dumps(
            [document.model_dump(mode="json") for document in documents],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(input_file),
            "--output-json",
            str(output_file),
            "--max-documents",
            "0",
        ]
    )

    payload = json.loads(output_file.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert [document["file_name"] for document in payload] == ["one.md", "two.md"]
    assert all(document["parent_chunks"] for document in payload)
    assert all(document["child_chunks"] for document in payload)


def test_chunk_documents_cli_returns_error_for_invalid_json(tmp_path):
    input_file = tmp_path / "broken.normalized.json"
    input_file.write_text("{not json", encoding="utf-8")

    exit_code = main([str(input_file)])

    assert exit_code == 1


def _normalized_document(file_name: str = "fixture.md") -> ParsedDocument:
    return DocumentNormalizer().normalize(
        ParsedDocument(
            title="Fixture",
            file_name=file_name,
            file_type=SupportedFileType.MARKDOWN,
            source_path=f"/tmp/{file_name}",
            blocks=[
                DocumentBlock(
                    block_type=BlockType.HEADING,
                    text="Fixture",
                    order=0,
                    level=1,
                    source_location=SourceLocation(line_start=1, line_end=1),
                ),
                DocumentBlock(
                    block_type=BlockType.HEADING,
                    text="Policy Table",
                    order=1,
                    level=2,
                    parent_path=["Fixture"],
                    source_location=SourceLocation(line_start=3, line_end=3),
                ),
                DocumentBlock(
                    block_type=BlockType.TABLE,
                    text=(
                        "| Policy ID | Rule |\n"
                        "| --- | --- |\n"
                        "| P-004 | Satellite mode syncs within 14 days. |"
                    ),
                    order=2,
                    parent_path=["Fixture", "Policy Table"],
                    source_location=SourceLocation(line_start=5, line_end=7),
                    metadata={"format": "markdown_table"},
                ),
            ],
        )
    )
