# Base44 Dev Environment

## Overview
A FastAPI backend ("Personal Learning Agent") with SQLite. No frontend — the preview serves the auto-generated Swagger docs at `/docs`. The app researches topics via the Anthropic API, teaches through rotating active-learning methods, and tracks effectiveness.

## Setup
- The app lives in `AI university project/` (subdirectory of repo root), not at the root.
- Run: `docker compose -f docker-compose.base44.yml up -d` from that directory.
- Uses `python:3.12-slim` base image with the source bind-mounted at `/app`; dependencies install at startup via pip. Uvicorn runs with `--reload` for live edits.
- SQLite DB is created automatically on startup (`data/learning_agent.db`); no migrations needed.
- Web entry point: host port 3000 → container 8000. Health check at `/health`.

## Secrets
- `ANTHROPIC_API_KEY` — required for all core features (research, teaching, grading). Delivered via the platform env file at `/run/base44/app.env`, loaded as the compose service's `env_file`. Do NOT also list it under compose `environment:` (that overrides the env file with an empty value).

## Verifying
- `curl -sf http://localhost:3000/health` → `{"status":"ok"}`
- Swagger UI: `http://localhost:3000/docs`
- Confirm the external hostname works: `curl -sf -H "Host: external-preview.example.com" http://localhost:3000/health` (CORS allows all origins).
