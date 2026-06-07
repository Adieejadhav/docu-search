from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.constants import BlockType, SupportedFileType, SUPPORTED_JSON_EXTENSIONS
from app.core.exceptions import ParserError
from app.ingestion.normalizers.block_schema import DocumentBlock, ParsedDocument
from app.ingestion.parsers.base import BaseDocumentParser


class JsonParser(BaseDocumentParser):
    """
    Parser for JSON files.

    JSON objects and arrays are recursively converted into JSON blocks with
    stable JSONPath-like metadata.
    """

    supported_extensions = SUPPORTED_JSON_EXTENSIONS

    def parse(self, file_path: str | Path) -> ParsedDocument:
        path = self.validate_input_file(file_path)
        content, encoding = self.read_text_with_fallback(
            path,
            failure_code="JSON_DECODE_FAILED",
        )

        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ParserError(
                f"Unable to parse JSON file: {path}",
                code="JSON_PARSE_FAILED",
                details={
                    "file_path": str(path),
                    "line": exc.lineno,
                    "column": exc.colno,
                    "reason": exc.msg,
                },
            ) from exc

        blocks = self._parse_value(parsed_json, path="$")

        return self.build_document(
            path=path,
            file_type=SupportedFileType.JSON,
            blocks=blocks,
            metadata={
                "encoding": encoding,
                "encoding_strategy": "configured text encoding fallback",
            },
        )

    def _parse_value(self, value: Any, *, path: str) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []
        self._append_value_blocks(blocks, value, path=path)

        for order, block in enumerate(blocks):
            blocks[order] = block.model_copy(update={"order": order})

        return blocks

    def _append_value_blocks(
        self,
        blocks: list[DocumentBlock],
        value: Any,
        *,
        path: str,
    ) -> None:
        if isinstance(value, dict):
            if self._is_scalar_mapping(value) or not value:
                self._append_json_block(blocks, value, path=path)
                return

            for key, child_value in value.items():
                self._append_value_blocks(
                    blocks,
                    child_value,
                    path=f"{path}.{self._escape_path_key(str(key))}",
                )
            return

        if isinstance(value, list):
            if self._is_scalar_sequence(value) or not value:
                self._append_json_block(blocks, value, path=path)
                return

            for index, child_value in enumerate(value):
                self._append_value_blocks(
                    blocks,
                    child_value,
                    path=f"{path}[{index}]",
                )
            return

        self._append_json_block(blocks, value, path=path)

    def _append_json_block(
        self,
        blocks: list[DocumentBlock],
        value: Any,
        *,
        path: str,
    ) -> None:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if not isinstance(value, dict | list):
            text = f"{path}: {text}"

        blocks.append(
            DocumentBlock(
                block_type=BlockType.JSON,
                text=text,
                order=len(blocks),
                metadata={
                    "json_path": path,
                    "value_type": type(value).__name__,
                },
            )
        )

    def _is_scalar_mapping(self, value: dict[Any, Any]) -> bool:
        return all(not isinstance(child, dict | list) for child in value.values())

    def _is_scalar_sequence(self, value: list[Any]) -> bool:
        return all(not isinstance(child, dict | list) for child in value)

    def _escape_path_key(self, key: str) -> str:
        if key.isidentifier():
            return key

        escaped_key = key.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped_key}"'
