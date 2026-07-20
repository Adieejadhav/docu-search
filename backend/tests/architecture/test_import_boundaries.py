from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

STALE_MODULES = {
    "app.embeddings",
    "app.indexing",
    "app.llm",
    "app.db",
    "app.chat.store",
    "app.search.service",
}


def test_removed_legacy_modules_are_not_imported_by_application_code():
    violations = []
    for path in python_files(APP_ROOT):
        for imported in imports_for(path):
            if matches_any(imported, STALE_MODULES):
                violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def test_api_does_not_import_low_level_technology_packages_directly():
    forbidden = {
        "psycopg",
        "sentence_transformers",
        "ollama",
        "app.integrations.embeddings.sentence_transformer",
        "app.integrations.llm.ollama",
    }
    violations = []
    for path in python_files(APP_ROOT / "api"):
        for imported in imports_for(path):
            if matches_any(imported, forbidden):
                violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def test_rag_and_ingestion_do_not_import_fastapi():
    violations = []
    for folder_name in ("rag", "ingestion"):
        for path in python_files(APP_ROOT / folder_name):
            for imported in imports_for(path):
                if imported == "fastapi" or imported.startswith("fastapi."):
                    violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def test_storage_and_integration_layers_do_not_import_api_modules():
    violations = []
    for folder_name in ("repositories", "integrations"):
        for path in python_files(APP_ROOT / folder_name):
            for imported in imports_for(path):
                if imported == "app.api" or imported.startswith("app.api."):
                    violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def imports_for(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def matches_any(imported: str, forbidden_modules: set[str]) -> bool:
    return any(
        imported == forbidden or imported.startswith(f"{forbidden}.")
        for forbidden in forbidden_modules
    )


def relative(path: Path) -> str:
    return str(path.relative_to(APP_ROOT.parent))
