# Document Ingestion Flow

## API Upload

```text
POST /admin/ingestion/jobs
  -> app/api/routes/ingestion.py
  -> IngestionService.create_upload_job()
  -> validate upload count and file names
  -> persist uploaded files under the configured upload root
  -> validate extension, size, and content type
  -> IngestionJobService.create_job()
  -> optionally schedule IngestionService.run_job() as a background task
```

The route still accepts the same multipart fields:

```text
files
clear_index
replace
continue_on_error
```

## Job Execution

```text
IngestionJobService.run_job()
  -> mark job running
  -> IngestionOrchestrator.ingest()
  -> discover source files
  -> ParserFactory selects parser by extension
  -> parser returns normalized ParsedDocument data
  -> parent-child chunker creates ParentChunk and ChildChunk records
  -> PgVectorChunkIndex indexes documents and embeddings
  -> progress events are appended to the job
  -> job is completed or failed
```

## Preserved Behavior

Supported upload extensions remain:

```text
.txt, .md, .markdown, .pdf, .docx, .pptx, .xlsx, .csv, .json
```

The ingestion service preserves existing upload size limits, max file count,
content validation, `background` versus `worker` run modes, and job response
schemas.
