from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import get_pipeline_node_tester
from app.core.constants import MAX_FILE_SIZE_BYTES
from app.core.exceptions import IngestionError
from app.ingestion.pipeline_testing import PipelineNodeTester, PipelineTestStage
from app.schemas import PipelineNodeTestResponse

router = APIRouter()


@router.post("/test", response_model=PipelineNodeTestResponse)
async def test_pipeline_node(
    stage: PipelineTestStage = Form(...),
    file: UploadFile = File(...),
    tester: PipelineNodeTester = Depends(get_pipeline_node_tester),
) -> PipelineNodeTestResponse:
    filename = Path(file.filename or "").name.strip()
    if not filename or filename in {".", ".."}:
        raise IngestionError(
            "A valid test file name is required",
            code="INVALID_PIPELINE_TEST_FILE_NAME",
        )

    with TemporaryDirectory(prefix="docu-search-pipeline-") as temporary_directory:
        file_path = Path(temporary_directory) / filename
        await _write_bounded_upload(file, file_path)
        result = tester.run(stage=stage, file_path=file_path)

    return PipelineNodeTestResponse(
        stage=result.stage,
        status="completed",
        duration_ms=result.duration_ms,
        summary=result.summary,
        preview=result.preview,
    )


async def _write_bounded_upload(upload: UploadFile, destination: Path) -> None:
    total_bytes = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE_BYTES:
                    raise IngestionError(
                        "Pipeline test file is too large",
                        code="PIPELINE_TEST_FILE_TOO_LARGE",
                        details={"max_file_size_bytes": MAX_FILE_SIZE_BYTES},
                    )
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
