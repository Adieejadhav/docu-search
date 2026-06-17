# Parser Next Iteration Plan

This document lists the remaining parser improvements found during real corpus testing. The current parser layer is working across all supported formats, but these items should be completed before calling the ingestion parser layer production-grade.

## Current Tested Baseline

| Format | Parser | Current result |
| --- | --- | --- |
| `.txt` | `TextParser` | Parsed paragraphs and list items correctly. |
| `.md`, `.markdown` | `MarkdownParser` | Parsed headings, tables, code, lists, and YAML front matter metadata correctly. |
| `.pdf` | `PdfParser` | Parsed all pages as page-level paragraph blocks. |
| `.docx` | `DocxParser` | Parsed paragraphs, headings, list items, and real DOCX tables correctly. |
| `.pptx` | `PptxParser` | Parsed all visible text blocks from slides correctly. |
| `.xlsx` | `XlsxParser` | Parsed worksheets as sheet headings plus row-level table blocks. |
| `.csv` | `CsvParser` | Parsed all logical CSV records as row-level table blocks. |
| `.json` | `JsonParser` | Parsed the full nested JSON corpus into JSONPath-addressed blocks. |

## Priority 1: Correctness And Traceability

These should be done first because they affect retrieval evidence and user trust.

### CSV Physical Line Locations

Current behavior:

- CSV records with quoted embedded newlines parse correctly.
- `line_start` and `line_end` currently behave like logical row numbers.

Needed:

- Track true physical file line ranges using the CSV reader line counter.
- Keep logical row number separately in metadata.
- Add tests for quoted multiline fields.

Done means:

- A row spanning physical lines `10-11` reports `line_start=10`, `line_end=11`.
- `metadata.row_number` remains the logical CSV data row number.

### DOCX Title Extraction

Current behavior:

- If core title is empty, title falls back to the first `Heading 1`.
- In the tested DOCX, the visible opening paragraph is a better document title than `Document Control`.

Needed:

- Prefer core title when present.
- Otherwise infer title from the first strong opening paragraph before the first heading.
- Fall back to first `Heading 1`, then filename.

Done means:

- The DOCX fixture title becomes the visible document title, not the first section heading.
- Existing DOCX title tests still pass.

### JSON Source Position Metadata

Current behavior:

- Blocks include stable JSONPath-like metadata.
- They do not include source line or character offsets.

Needed:

- Add optional JSON source line and character position metadata where practical.
- If exact offsets are not feasible with the standard parser, document that limitation and add stable path-based evidence references.

Done means:

- JSON blocks can be cited by `json_path` plus source position when available.
- Long JSON fields still preserve full text.

## Priority 2: Semantic Structure

These improve retrieval quality by making blocks closer to how humans read the documents.

### PPTX Title And Layout Inference

Current behavior:

- The PPTX fixture exposes most content as independent text boxes.
- Parser captures all text, but emits all blocks as paragraphs for that fixture.

Needed:

- Infer slide title from top-most or largest text when no title placeholder exists.
- Group table-like text boxes by row and column coordinates.
- Preserve shape coordinates in metadata.
- Detect repeated footer/header text.

Done means:

- The PPTX fixture emits meaningful slide heading blocks.
- Visual table-like slide content becomes table blocks when confidence is high.
- False table detection remains low.

### DOCX Rich Content

Current behavior:

- Real body tables, headings, paragraphs, and list-style items are parsed.

Needed:

- Parse headers, footers, footnotes, endnotes, comments, and text boxes when present.
- Preserve page breaks and section breaks as metadata or boundary blocks.
- Capture actual list numbering where Word exposes it.
- Handle nested tables.

Done means:

- DOCX fixtures with headers, footnotes, text boxes, and nested tables have explicit blocks.
- Body-order parsing remains stable.

### PDF Layout-Aware Parsing

Current behavior:

- One paragraph block per page.

Needed:

- Split pages into paragraph-like blocks where text layout supports it.
- Detect tables or table-like text regions.
- Add OCR fallback strategy for image-only PDFs.
- Add metadata for page count, encrypted status, extraction mode, and OCR status.

Done means:

- Text PDFs produce smaller evidence-friendly blocks.
- Image-only PDFs fail with a clear typed error or use OCR if configured.

## Priority 3: Format-Specific Quality

These are important but can follow the correctness and semantic work.

### XLSX Formula And Sheet Semantics

Needed:

- Preserve formula text and cached values when available.
- Track hidden sheets, hidden rows, hidden columns, merged cells, and named tables.
- Keep native value types and display values in metadata.
- Add optional row batching for very large sheets.

Done means:

- Formula cells are not silently flattened without metadata.
- Hidden or merged content is represented intentionally.

### Markdown Edge Cases

Already fixed:

- YAML front matter is metadata, not a fake heading.

Needed:

- Parse footnotes into metadata or dedicated blocks.
- Decide policy for inline HTML: preserve raw text, sanitize, or emit HTML metadata.
- Improve nested list ancestry if list structure is needed by downstream retrieval.

Done means:

- Footnote references and definitions can be retrieved and cited cleanly.
- Inline HTML behavior is explicit and tested.

### TXT Section Detection

Needed:

- Optionally detect all-caps or underline-style section headings.
- Keep conservative defaults to avoid false headings in logs.

Done means:

- Plain text operational docs get useful section hierarchy when obvious.
- Log-like text remains paragraph/code-like text.

## Priority 4: Operational Hardening

These make the parser system safer to run on real folders and large inputs.

### File Discovery And Skips

Already fixed:

- CLI folder scans skip Office lock files like `~$...`.

Needed:

- Report skipped files with reason when running directory scans.
- Add skip rules for common temp/partial files if needed.

Done means:

- Folder parsing reports parsed, failed, and skipped counts separately.

### Observability

Current behavior:

- Parser success/failure logs and in-memory metrics exist.

Needed:

- Add structured metric names for parse duration, block count, bytes read, skipped files, and failure codes.
- Support a real metrics sink later without changing parser APIs.
- Include parser version or schema version in metadata.

Done means:

- Each parse can be monitored by parser type, file type, success/failure, duration, and block count.

### Large File Controls

Needed:

- Add parser-level maximum block count safeguards.
- Add streaming or chunked parsing for large CSV/JSON where possible.
- Add CLI options for output file, max blocks, and summary-only mode.

Done means:

- Large files do not accidentally flood terminal output or memory.
- Full output can always be written to an artifact file.

## Priority 5: Evaluation And Regression Coverage

Needed:

- Keep the robust corpus as golden fixtures.
- Store expected summary counts per fixture.
- Add tests that compare parser summaries, not random UUIDs.
- Add tests for bad files, wrong extensions, corrupted Office files, unreadable files, and empty documents.

Done means:

- A single test command proves every supported parser still meets its expected contract.
- Parser changes cannot silently regress block counts, metadata, or source references.

## Suggested Execution Order

1. CSV physical line ranges.
2. DOCX title extraction.
3. PPTX slide title inference.
4. JSON source references or documented path-only evidence policy.
5. PDF layout-aware block splitting.
6. DOCX rich content: headers, footers, footnotes, text boxes.
7. XLSX formula and hidden/merged cell metadata.
8. Markdown footnotes and inline HTML policy.
9. Operational skip reporting and metrics hardening.
10. Golden corpus regression tests.

## Completion Target

After these items are done, the parser layer should be considered a strong production baseline:

- All supported files parse deterministically.
- Every block has meaningful type, text, order, metadata, and source reference.
- Folder parsing is resilient to temp files and bad inputs.
- Full outputs can be inspected without terminal truncation.
- Regression tests cover all supported formats and known edge cases.
