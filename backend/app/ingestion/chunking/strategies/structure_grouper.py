"""
File: backend/app/ingestion/chunking/strategies/structure_grouper.py
Purpose: Groups normalized blocks by document structure before chunk splitting.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.constants import BlockType, SupportedFileType
from app.ingestion.normalizers.block_schema import DocumentBlock, ParsedDocument
from app.ingestion.validators.block_validator import is_block_type

from .base import StructureGroup


class StructureGrouper:
    """
    Converts normalized blocks into logical parent candidates.

    The grouping prefers explicit heading paths. When a format has weak heading
    structure, it falls back to page, slide, sheet, row-table, or JSON path
    boundaries from normalized source metadata.
    """

    JSON_PATH_TOKEN_PATTERN = re.compile(r"\[(\d+)\]|\.([^.\[]+)")

    def group(self, document: ParsedDocument) -> list[StructureGroup]:
        groups: list[StructureGroup] = []

        for block in document.blocks:
            key, title, parent_path, metadata = self._identity(document, block)
            if groups and groups[-1].key == key:
                groups[-1].blocks.append(block)
                continue

            groups.append(
                StructureGroup(
                    key=key,
                    title=title,
                    parent_path=parent_path,
                    blocks=[block],
                    metadata=metadata,
                )
            )

        return groups

    def _identity(
        self,
        document: ParsedDocument,
        block: DocumentBlock,
    ) -> tuple[str, str, list[str], dict[str, Any]]:
        heading_path = self._heading_path(block)
        if heading_path:
            return (
                "heading:" + " > ".join(heading_path),
                heading_path[-1],
                heading_path,
                {"structure": "heading_path"},
            )

        location = block.source_location

        if location.page_number is not None:
            title = f"Page {location.page_number}"
            return (
                f"page:{location.page_number}",
                title,
                [title],
                {"structure": "page", "page_number": location.page_number},
            )

        if location.slide_number is not None:
            title = f"Slide {location.slide_number}"
            return (
                f"slide:{location.slide_number}",
                title,
                [title],
                {"structure": "slide", "slide_number": location.slide_number},
            )

        sheet_name = location.sheet_name or block.metadata.get("sheet_name")
        if sheet_name:
            title = str(sheet_name)
            return (
                f"sheet:{title}",
                title,
                [title],
                {"structure": "sheet", "sheet_name": title},
            )

        json_path = block.metadata.get("json_path")
        if json_path:
            parent_path = self._json_parent_path(str(json_path))
            return (
                "json:" + " > ".join(parent_path),
                parent_path[-1],
                parent_path,
                {"structure": "json_path", "json_path_prefix": parent_path[-1]},
            )

        if document.file_type == SupportedFileType.CSV.value:
            return (
                "csv:rows",
                document.title,
                [document.title],
                {"structure": "csv_rows"},
            )

        return (
            "document:root",
            document.title,
            [document.title],
            {"structure": "document_root"},
        )

    def _heading_path(self, block: DocumentBlock) -> list[str]:
        if is_block_type(block.block_type, BlockType.HEADING):
            return [*block.parent_path, block.text]

        return list(block.parent_path)

    def _json_parent_path(self, json_path: str) -> list[str]:
        if not json_path or json_path == "$":
            return ["$"]

        parts: list[str] = ["$"]
        for match in self.JSON_PATH_TOKEN_PATTERN.finditer(json_path):
            index_token, key_token = match.groups()
            parts.append(f"[{index_token}]" if index_token is not None else key_token)
            if len(parts) >= 3:
                break

        return parts or ["$"]
