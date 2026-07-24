from __future__ import annotations

from app.core.logging import (
    format_external_http_log,
    format_field_lines,
    format_request_log,
    parse_http_request_log,
    single_line,
)


def test_single_line_collapses_multiline_log_text():
    assert single_line("first line\nsecond\tline\r\nthird line") == (
        "first line second line third line"
    )


def test_format_request_log_keeps_success_compact():
    assert format_request_log(
        timestamp="2026-07-24T10:46:28Z",
        method="GET",
        path="/chat/sessions",
        status_code=200,
        duration_ms=11.717,
        request_id="dc248829-d4f3-47af-8509-0c1f9eef0184",
    ) == "2026-07-24T10:46:28Z GET /chat/sessions 200 11.7ms"


def test_format_request_log_keeps_short_request_id_for_errors():
    assert format_request_log(
        timestamp="2026-07-24T10:46:28Z",
        method="POST",
        path="/admin/ingestion/jobs",
        status_code=400,
        duration_ms=22.1,
        request_id="dc248829-d4f3-47af-8509-0c1f9eef0184",
    ) == "2026-07-24T10:46:28Z POST /admin/ingestion/jobs 400 22.1ms rid=dc248829"


def test_format_request_log_expands_long_paths():
    formatted = format_request_log(
        timestamp="2026-07-24T10:46:28Z",
        method="GET",
        path="/admin/ingestion/jobs/" + "a" * 120,
        status_code=200,
        duration_ms=3.141,
    )

    assert formatted.splitlines()[0] == "2026-07-24T10:46:28Z request"
    assert "  method=GET" in formatted
    assert "  status=200" in formatted
    assert "  duration=3.1ms" in formatted


def test_parse_and_format_huggingface_httpx_log():
    details = parse_http_request_log(
        'HTTP Request: HEAD https://huggingface.co/api/resolve-cache/models/'
        'BAAI/bge-small-en-v1.5/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/'
        'config_sentence_transformers.json "HTTP/1.1 200 OK"'
    )

    assert details is not None
    formatted = format_external_http_log(
        timestamp="2026-07-24T10:01:57Z",
        level="INFO",
        details=details,
    )

    assert formatted == (
        "2026-07-24T10:01:57Z INFO external_http\n"
        "  method=HEAD\n"
        "  host=huggingface.co\n"
        "  model=BAAI/bge-small-en-v1.5\n"
        "  revision=5c38ec7c405ec4b44b94cc5a9bb96e735b38267a\n"
        "  file=config_sentence_transformers.json\n"
        "  status=200\n"
        "  reason=OK"
    )


def test_format_field_lines_wraps_long_path_values():
    lines = format_field_lines(
        "path",
        "/api/resolve-cache/models/BAAI/bge-small-en-v1.5/"
        "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/config_sentence_transformers.json",
    )

    assert len(lines) > 1
    assert lines[0].startswith("  path=")
    assert lines[1].startswith("    ")
