from __future__ import annotations

import pytest

from app.core.constants import BlockType, SupportedFileType
from app.core.exceptions import EmptyDocumentError, UnsupportedFileTypeError
from app.ingestion.parsers.text_parser import TextParser


def test_text_parser_creates_paragraph_and_list_blocks(tmp_path):
    file_path = tmp_path / "team-notes.txt"
    file_path.write_text(
        "First paragraph line one\n"
        "continues here.\n"
        "\n"
        "- item one\n"
        "2. item two\n"
        "\n"
        "Final paragraph.\n",
        encoding="utf-8",
    )

    document = TextParser().parse(file_path)

    assert document.title == "team-notes"
    assert document.file_name == "team-notes.txt"
    assert document.file_type == SupportedFileType.TXT.value
    assert document.metadata["encoding"] == "utf-8"
    assert [block.block_type for block in document.blocks] == [
        BlockType.PARAGRAPH.value,
        BlockType.LIST_ITEM.value,
        BlockType.LIST_ITEM.value,
        BlockType.PARAGRAPH.value,
    ]
    assert [block.order for block in document.blocks] == [0, 1, 2, 3]
    assert document.blocks[0].text == "First paragraph line one continues here."
    assert document.blocks[0].source_location.line_start == 1
    assert document.blocks[0].source_location.line_end == 2
    assert document.blocks[1].metadata["marker"] == "-"
    assert document.blocks[2].metadata["marker"] == "2."


def test_text_parser_rejects_unsupported_extension(tmp_path):
    file_path = tmp_path / "notes.md"
    file_path.write_text("# Notes\n", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError) as error:
        TextParser().parse(file_path)

    assert error.value.code == "UNSUPPORTED_FILE_TYPE"


def test_text_parser_rejects_whitespace_only_document(tmp_path):
    file_path = tmp_path / "blank.txt"
    file_path.write_text(" \n\t\n", encoding="utf-8")

    with pytest.raises(EmptyDocumentError) as error:
        TextParser().parse(file_path)

    assert error.value.code == "EMPTY_DOCUMENT"
