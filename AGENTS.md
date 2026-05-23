# Repository Guidelines

## Project Structure & Module Organization

This repository contains a FastAPI backend for the VaaniAI healthcare receptionist MVP.

- `app/` contains application code.
- `app/main.py` defines HTTP routes such as `/chat`, `/doctors`, `/dashboard/metrics`, `/transcripts`, `/transcribe`, and `/tts`.
- `app/models.py` and `app/schemas.py` define SQLModel database models and Pydantic request/response schemas.
- `app/services.py` contains booking, dashboard, transcript, and conversation state-machine logic.
- `app/intent.py` contains rule-based intent and slot parsing helpers.
- `app/audio.py` contains STT/TTS wrapper placeholders.
- `scripts/seed_demo_data.py` seeds demo doctors and slots.
- `tests/` contains pytest coverage for API behavior, chat flow, and intent parsing.
- `VaaniAI.pdf` and `VaaniAI.txt` are project reference documents. Do not modify them unless the product brief changes.

## Build, Test, and Development Commands

Create or update the local Python environment:

```powershell
pip install -r requirements.txt
```

Run the API locally:

```powershell
python -m uvicorn app.main:app --reload
```

Seed demo data:

```powershell
python scripts\seed_demo_data.py
```

Run the test suite:

```powershell
pytest -q
```

Use `http://127.0.0.1:8000/docs` for interactive API testing while developing.

## Coding Style & Naming Conventions

Use Python 3 style with 4-space indentation, type hints for public functions, and clear module boundaries. Keep route handlers thin; place business logic in `app/services.py` or focused helper modules. Use `snake_case` for functions, variables, and database fields. Use `PascalCase` for SQLModel and Pydantic classes. Keep response schemas explicit instead of returning unstructured dictionaries from new endpoints.

## Testing Guidelines

Tests use `pytest` and FastAPI/httpx test utilities. Add or update tests for every route, state-machine transition, parser rule, or booking behavior change. Name test files `test_*.py` and test functions `test_*`. Prefer focused tests such as `test_chat_flow.py` for conversation behavior and `test_intent.py` for language/time parsing.

## Commit & Pull Request Guidelines

No git history is present in this workspace. Use concise imperative commit messages, for example `Add dashboard metrics endpoint` or `Fix Hindi slot parsing`. Pull requests should include a short summary, test results (`pytest -q`), affected endpoints, and any configuration or migration notes. Include screenshots only for frontend/dashboard UI changes.

## Security & Configuration Tips

The default database is local SQLite (`vaaniai.db`). Override `DATABASE_URL` when using another database. Do not commit secrets, API keys, model weights, generated audio files, or production call data. Keep STT/TTS integrations behind service wrappers in `app/audio.py` so provider-specific code remains isolated.
