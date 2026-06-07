from __future__ import annotations

import pytest

from app.core.exceptions import FileValidationError
from app.ingestion.validators.file_validator import validate_local_file


def test_validate_local_file_accepts_extensions_without_dot(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("content", encoding="utf-8")

    validated_file = validate_local_file(file_path, supported_extensions={"txt"})

    assert validated_file.file_path == file_path
    assert validated_file.file_name == "notes.txt"
    assert validated_file.extension == ".txt"
    assert validated_file.size_bytes > 0
    assert validated_file.detected_content_type == "text"
    assert validated_file.media_type == "text/plain"


def test_validate_local_file_rejects_empty_file(tmp_path):
    file_path = tmp_path / "empty.txt"
    file_path.write_text("", encoding="utf-8")

    with pytest.raises(FileValidationError) as error:
        validate_local_file(file_path)

    assert error.value.code == "EMPTY_FILE"


def test_validate_local_file_rejects_unsupported_extension(tmp_path):
    file_path = tmp_path / "notes.exe"
    file_path.write_text("content", encoding="utf-8")

    with pytest.raises(FileValidationError) as error:
        validate_local_file(file_path)

    assert error.value.code == "UNSUPPORTED_FILE_TYPE"


def test_validate_local_file_rejects_text_renamed_as_pdf(tmp_path):
    file_path = tmp_path / "fake.pdf"
    file_path.write_text("I am not a PDF", encoding="utf-8")

    with pytest.raises(FileValidationError) as error:
        validate_local_file(file_path)

    assert error.value.code == "FILE_CONTENT_TYPE_MISMATCH"
    assert error.value.details["extension"] == ".pdf"
    assert error.value.details["detected_content_type"] == "text"


def test_validate_local_file_rejects_invalid_json_content(tmp_path):
    file_path = tmp_path / "broken.json"
    file_path.write_text("{not valid json}", encoding="utf-8")

    with pytest.raises(FileValidationError) as error:
        validate_local_file(file_path)

    assert error.value.code == "FILE_CONTENT_TYPE_MISMATCH"
    assert error.value.details["extension"] == ".json"
    assert error.value.details["invalid_json"] is True
