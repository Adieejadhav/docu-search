# Backend

Backend service for the Docu Search RAG application.

Current source layout follows the modular structure in `docs/backend-folder-guide.md`:

```text
app/
migrations/
scripts/
tests/
docs/
```

Run validation from this directory with:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .tmp\pytest
```
