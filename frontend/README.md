# Docu Search Frontend

Browser console for testing the FastAPI RAG backend.

## Run

Start the backend:

```powershell
cd C:\docu-search\backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend:

```powershell
cd C:\docu-search\frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Structure

```text
src/app        application shell and navigation
src/components shared UI building blocks
src/features   feature-specific screens
src/lib        formatting and utility functions
src/services   API client and HTTP DTO types
```

Sections:

```text
Chat   end-user document chat only
Admin  health, index documents, RAG testing, performance, and index clear
```
