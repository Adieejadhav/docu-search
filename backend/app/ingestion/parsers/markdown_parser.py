from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token
import yaml

from app.core.constants import (
    BlockType,
    SupportedFileType,
    SUPPORTED_MARKDOWN_EXTENSIONS,
)
from app.ingestion.normalizers.block_schema import (
    DocumentBlock,
    ParsedDocument,
    SourceLocation,
)
from app.ingestion.parsers.base import BaseDocumentParser


class MarkdownParser(BaseDocumentParser):
    """
    Markdown parser backed by markdown-it-py tokenization.

    This parser converts Markdown tokens into the normalized document block
    schema while preserving line locations and heading ancestry.
    """

    supported_extensions = SUPPORTED_MARKDOWN_EXTENSIONS

    LIST_MARKER_PATTERN = re.compile(
        r"^(?P<indent>\s*)(?P<marker>-|\*|\+|\d+[.)])\s+"
    )
    FRONT_MATTER_DELIMITER = "---"
    FRONT_MATTER_END_DELIMITERS = {"---", "..."}

    def __init__(self) -> None:
        self._markdown = MarkdownIt("default", {"html": False})

    def parse(self, file_path: str | Path) -> ParsedDocument:
        path = self.validate_input_file(file_path)
        content, encoding = self.read_text_with_fallback(
            path,
            failure_code="MARKDOWN_DECODE_FAILED",
        )

        lines = content.splitlines()
        front_matter, parse_content = self._extract_front_matter(content, lines)
        tokens = self._markdown.parse(parse_content)
        blocks = self._tokens_to_blocks(tokens, lines)
        title = self._extract_title(blocks) or self.get_document_title(path)
        metadata: dict[str, Any] = {
            "encoding": encoding,
            "encoding_strategy": "configured text encoding fallback",
            "markdown_engine": "markdown-it-py",
        }
        if front_matter is not None:
            metadata.update(front_matter)

        return self.build_document(
            path=path,
            title=title,
            file_type=SupportedFileType.MARKDOWN,
            blocks=blocks,
            metadata=metadata,
        )

    def _extract_front_matter(
        self,
        content: str,
        lines: list[str],
    ) -> tuple[dict[str, Any] | None, str]:
        if not lines or lines[0].strip() != self.FRONT_MATTER_DELIMITER:
            return None, content

        closing_index = self._front_matter_closing_index(lines)
        if closing_index is None:
            return None, content

        raw_front_matter = "\n".join(lines[1:closing_index])
        metadata: dict[str, Any] = {
            "front_matter": self._parse_front_matter(raw_front_matter),
            "front_matter_source": {
                "line_start": 1,
                "line_end": closing_index + 1,
            },
        }

        parse_lines = lines.copy()
        for line_index in range(0, closing_index + 1):
            parse_lines[line_index] = ""

        parse_content = "\n".join(parse_lines)
        if content.endswith(("\n", "\r")):
            parse_content += "\n"

        return metadata, parse_content

    def _front_matter_closing_index(self, lines: list[str]) -> int | None:
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() in self.FRONT_MATTER_END_DELIMITERS:
                return index

        return None

    def _parse_front_matter(self, raw_front_matter: str) -> dict[str, Any]:
        if not raw_front_matter.strip():
            return {}

        parsed = yaml.safe_load(raw_front_matter)
        if parsed is None:
            return {}

        if isinstance(parsed, dict):
            return {
                str(key): self._json_safe_metadata_value(value)
                for key, value in parsed.items()
            }

        return {"value": self._json_safe_metadata_value(parsed)}

    def _json_safe_metadata_value(self, value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value

        if isinstance(value, list):
            return [self._json_safe_metadata_value(item) for item in value]

        if isinstance(value, tuple | set):
            return [self._json_safe_metadata_value(item) for item in value]

        if isinstance(value, dict):
            return {
                str(key): self._json_safe_metadata_value(item)
                for key, item in value.items()
            }

        return str(value)

    def _tokens_to_blocks(
        self,
        tokens: list[Token],
        lines: list[str],
    ) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []
        heading_stack: dict[int, str] = {}
        list_item_depth = 0

        index = 0
        while index < len(tokens):
            token = tokens[index]

            if token.type == "heading_open":
                block, next_index = self._build_heading_block(
                    tokens,
                    index,
                    heading_stack,
                )
                if block is not None:
                    blocks.append(block.model_copy(update={"order": len(blocks)}))
                index = next_index
                continue

            if token.type == "paragraph_open" and list_item_depth == 0:
                block, next_index = self._build_paragraph_block(
                    tokens,
                    index,
                    heading_stack,
                )
                if block is not None:
                    blocks.append(block.model_copy(update={"order": len(blocks)}))
                index = next_index
                continue

            if token.type == "list_item_open":
                list_item_depth += 1
                block = self._build_list_item_block(tokens, index, lines, heading_stack)
                if block is not None:
                    blocks.append(block.model_copy(update={"order": len(blocks)}))
                index += 1
                continue

            if token.type == "list_item_close":
                list_item_depth = max(0, list_item_depth - 1)
                index += 1
                continue

            if token.type == "fence":
                block = self._build_code_block(token, heading_stack)
                if block is not None:
                    blocks.append(block.model_copy(update={"order": len(blocks)}))
                index += 1
                continue

            if token.type == "table_open":
                block = self._build_table_block(token, lines, heading_stack)
                if block is not None:
                    blocks.append(block.model_copy(update={"order": len(blocks)}))
                index += 1
                continue

            index += 1

        return blocks

    def _build_heading_block(
        self,
        tokens: list[Token],
        start_index: int,
        heading_stack: dict[int, str],
    ) -> tuple[DocumentBlock | None, int]:
        token = tokens[start_index]
        level = self._heading_level(token)
        content, close_index = self._collect_inline_content(
            tokens,
            start_index,
            close_type="heading_close",
        )
        text = content.strip()

        if not text:
            return None, close_index + 1

        parent_path = [
            heading_stack[parent_level]
            for parent_level in sorted(heading_stack)
            if parent_level < level
        ]

        heading_stack[level] = text
        for existing_level in list(heading_stack):
            if existing_level > level:
                del heading_stack[existing_level]

        line_start, line_end = self._source_lines(token)
        return (
            DocumentBlock(
                block_type=BlockType.HEADING,
                text=text,
                order=0,
                level=level,
                parent_path=parent_path,
                source_location=SourceLocation(
                    line_start=line_start,
                    line_end=line_end,
                ),
            ),
            close_index + 1,
        )

    def _build_paragraph_block(
        self,
        tokens: list[Token],
        start_index: int,
        heading_stack: dict[int, str],
    ) -> tuple[DocumentBlock | None, int]:
        token = tokens[start_index]
        content, close_index = self._collect_inline_content(
            tokens,
            start_index,
            close_type="paragraph_close",
        )
        text = content.strip()

        if not text:
            return None, close_index + 1

        line_start, line_end = self._source_lines(token)
        return (
            DocumentBlock(
                block_type=BlockType.PARAGRAPH,
                text=text,
                order=0,
                parent_path=self._current_parent_path(heading_stack),
                source_location=SourceLocation(
                    line_start=line_start,
                    line_end=line_end,
                ),
            ),
            close_index + 1,
        )

    def _build_list_item_block(
        self,
        tokens: list[Token],
        start_index: int,
        lines: list[str],
        heading_stack: dict[int, str],
    ) -> DocumentBlock | None:
        token = tokens[start_index]
        text, paragraph_token = self._extract_list_item_text(tokens, start_index)
        text = text.strip()

        if not text:
            return None

        line_start, line_end = self._source_lines(paragraph_token or token)
        indent, marker, raw_line = self._list_marker_metadata(lines, line_start)

        return DocumentBlock(
            block_type=BlockType.LIST_ITEM,
            text=text,
            order=0,
            parent_path=self._current_parent_path(heading_stack),
            source_location=SourceLocation(
                line_start=line_start,
                line_end=line_end,
            ),
            metadata={
                "indent": indent,
                "marker": marker,
                "raw_line": raw_line,
            },
        )

    def _build_code_block(
        self,
        token: Token,
        heading_stack: dict[int, str],
    ) -> DocumentBlock | None:
        text = token.content.strip()
        if not text:
            return None

        line_start, line_end = self._source_lines(token)
        return DocumentBlock(
            block_type=BlockType.CODE,
            text=text,
            order=0,
            parent_path=self._current_parent_path(heading_stack),
            source_location=SourceLocation(
                line_start=line_start,
                line_end=line_end,
            ),
            metadata={
                "language": token.info.strip() or None,
                "markup": token.markup,
            },
        )

    def _build_table_block(
        self,
        token: Token,
        lines: list[str],
        heading_stack: dict[int, str],
    ) -> DocumentBlock | None:
        line_start, line_end = self._source_lines(token)
        if line_start is None or line_end is None:
            return None

        text = "\n".join(lines[line_start - 1 : line_end]).strip()
        if not text:
            return None

        return DocumentBlock(
            block_type=BlockType.TABLE,
            text=text,
            order=0,
            parent_path=self._current_parent_path(heading_stack),
            source_location=SourceLocation(
                line_start=line_start,
                line_end=line_end,
            ),
            metadata={"format": "markdown_table"},
        )

    def _collect_inline_content(
        self,
        tokens: list[Token],
        start_index: int,
        *,
        close_type: str,
    ) -> tuple[str, int]:
        content_parts: list[str] = []
        index = start_index + 1

        while index < len(tokens):
            token = tokens[index]
            if token.type == close_type:
                return " ".join(content_parts), index

            if token.type == "inline" and token.content:
                content_parts.append(token.content)

            index += 1

        return " ".join(content_parts), len(tokens) - 1

    def _extract_list_item_text(
        self,
        tokens: list[Token],
        start_index: int,
    ) -> tuple[str, Token | None]:
        item_token = tokens[start_index]
        item_level = item_token.level
        content_parts: list[str] = []
        paragraph_token: Token | None = None
        index = start_index + 1

        while index < len(tokens):
            token = tokens[index]
            if token.type == "list_item_close" and token.level == item_level:
                break

            if token.type in {"bullet_list_open", "ordered_list_open"}:
                if token.level > item_level + 1:
                    index = self._skip_nested_list(tokens, index)
                    continue

            if token.type == "paragraph_open" and paragraph_token is None:
                paragraph_token = token

            if (
                token.type == "inline"
                and token.content
                and token.level <= item_level + 2
            ):
                content_parts.append(token.content)

            index += 1

        return " ".join(content_parts), paragraph_token

    def _skip_nested_list(self, tokens: list[Token], start_index: int) -> int:
        opening_type = tokens[start_index].type
        closing_type = (
            "bullet_list_close"
            if opening_type == "bullet_list_open"
            else "ordered_list_close"
        )
        opening_level = tokens[start_index].level
        index = start_index + 1

        while index < len(tokens):
            token = tokens[index]
            if token.type == closing_type and token.level == opening_level:
                return index + 1
            index += 1

        return index

    def _heading_level(self, token: Token) -> int:
        if token.tag.startswith("h") and token.tag[1:].isdigit():
            return int(token.tag[1:])
        return 1

    def _source_lines(self, token: Token) -> tuple[int | None, int | None]:
        if token.map is None:
            return None, None

        start, end = token.map
        return start + 1, end

    def _list_marker_metadata(
        self,
        lines: list[str],
        line_start: int | None,
    ) -> tuple[int, str | None, str | None]:
        if line_start is None or line_start < 1 or line_start > len(lines):
            return 0, None, None

        raw_line = lines[line_start - 1].strip()
        match = self.LIST_MARKER_PATTERN.match(lines[line_start - 1])
        if match is None:
            return 0, None, raw_line

        return len(match.group("indent")), match.group("marker"), raw_line

    def _current_parent_path(self, heading_stack: dict[int, str]) -> list[str]:
        return [
            heading_stack[level]
            for level in sorted(heading_stack)
            if heading_stack.get(level)
        ]

    def _extract_title(self, blocks: list[DocumentBlock]) -> str | None:
        for block in blocks:
            if block.block_type == BlockType.HEADING and block.level == 1:
                return block.text

        return None
