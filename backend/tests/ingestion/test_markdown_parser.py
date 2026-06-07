from __future__ import annotations

from app.core.constants import BlockType, SupportedFileType
from app.ingestion.parsers.markdown_parser import MarkdownParser


def test_markdown_parser_extracts_yaml_front_matter_as_metadata(tmp_path):
    file_path = tmp_path / "knowledge-base.md"
    file_path.write_text(
        "---\n"
        'title: "Knowledge Base Metadata Title"\n'
        'doc_type: "runbook"\n'
        "version: 3.4.1\n"
        "owners: [GridOps, DataOps]\n"
        "tags: [rag-test, markdown]\n"
        "---\n"
        "\n"
        "# Visible Document Title\n"
        "\n"
        "Intro paragraph.\n"
        "\n"
        "## Policy Table\n"
        "\n"
        "| Policy | Owner |\n"
        "|---|---|\n"
        "| P-001 | GridOps |\n",
        encoding="utf-8",
    )

    document = MarkdownParser().parse(file_path)

    assert document.file_type == SupportedFileType.MARKDOWN.value
    assert document.title == "Visible Document Title"
    assert document.metadata["front_matter"] == {
        "title": "Knowledge Base Metadata Title",
        "doc_type": "runbook",
        "version": "3.4.1",
        "owners": ["GridOps", "DataOps"],
        "tags": ["rag-test", "markdown"],
    }
    assert document.metadata["front_matter_source"] == {
        "line_start": 1,
        "line_end": 7,
    }
    assert [block.block_type for block in document.blocks] == [
        BlockType.HEADING.value,
        BlockType.PARAGRAPH.value,
        BlockType.HEADING.value,
        BlockType.TABLE.value,
    ]
    assert document.blocks[0].text == "Visible Document Title"
    assert document.blocks[0].source_location.line_start == 9
    assert document.blocks[3].source_location.line_start == 15
    assert document.blocks[3].source_location.line_end == 17
