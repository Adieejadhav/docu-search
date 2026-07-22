from __future__ import annotations

import ast
import importlib
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


def test_api_modules_do_not_contain_raw_sql():
    sql_words = {"SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"}
    violations = []
    for path in python_files(APP_ROOT / "api"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                words = set(node.value.upper().replace("\n", " ").split())
                if words & sql_words:
                    violations.append(f"{relative(path)} contains SQL-like text")

    assert violations == []


def test_services_and_core_do_not_import_forbidden_upper_layers():
    violations = []
    checks = {
        "services": {"app.api"},
        "core": {"app.api", "app.services", "app.rag", "app.ingestion"},
    }
    for folder_name, forbidden in checks.items():
        for path in python_files(APP_ROOT / folder_name):
            for imported in imports_for(path):
                if matches_any(imported, forbidden):
                    violations.append(f"{relative(path)} imports {imported}")

    assert violations == []


def test_main_remains_composition_focused():
    main_path = APP_ROOT / "main.py"
    assert line_count(main_path) <= 80
    assert "connect_postgres" not in main_path.read_text(encoding="utf-8")


def test_endpoint_modules_import_successfully():
    endpoints_root = APP_ROOT / "api" / "v1" / "endpoints"
    for path in python_files(endpoints_root):
        module = dotted_module(path)
        importlib.import_module(module)


def test_dependency_factories_use_application_container():
    dependencies_path = APP_ROOT / "api" / "dependencies.py"
    source = dependencies_path.read_text(encoding="utf-8")
    assert "ApplicationContainer" in source
    for factory_name in (
        "get_search_service",
        "get_chat_service",
        "get_document_service",
        "get_ingestion_service",
        "get_trace_service",
        "get_admin_service",
        "get_health_service",
    ):
        assert f"def {factory_name}" in source


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


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def dotted_module(path: Path) -> str:
    return ".".join(path.relative_to(APP_ROOT.parent).with_suffix("").parts)
