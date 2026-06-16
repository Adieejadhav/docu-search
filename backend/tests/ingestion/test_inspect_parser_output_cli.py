from __future__ import annotations

import json

from app.cli.parse_documents import main


def test_inspect_parser_output_skips_office_lock_files_in_directory(tmp_path):
    input_file = tmp_path / "fixture.json"
    lock_file = tmp_path / "~$fixture.json"
    output_file = tmp_path / "parsed.json"
    input_file.write_text('{"status": "ok"}', encoding="utf-8")
    lock_file.write_text('{"status": "should be ignored"}', encoding="utf-8")

    exit_code = main(
        [
            str(tmp_path),
            "--output-json",
            str(output_file),
            "--max-blocks",
            "1",
            "--no-logs",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["file_name"] == "fixture.json"
    assert payload["metadata"]["block_count"] == 1
    assert payload["blocks"][0]["text"] == '{"status": "ok"}'


def test_inspect_parser_output_writes_complete_json_file(tmp_path):
    input_file = tmp_path / "fixture.json"
    output_file = tmp_path / "parsed" / "fixture.parsed.json"
    input_file.write_text('{"status": "ok", "count": 2}', encoding="utf-8")

    exit_code = main(
        [
            str(input_file),
            "--output-json",
            str(output_file),
            "--max-blocks",
            "1",
            "--no-logs",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["file_name"] == "fixture.json"
    assert payload["metadata"]["block_count"] == 1
    assert payload["blocks"][0]["metadata"]["json_path"] == "$"
    assert payload["blocks"][0]["text"] == '{"count": 2, "status": "ok"}'
