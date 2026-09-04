# Base44 Dev Environment

## Overview
A FastAPI backend ("Personal Learning Agent") with SQLite, plus a React/Vite frontend.
The backend researches topics via the Anthropic API, teaches through rotating active-learning
methods, and tracks effectiveness. The frontend is a calm, editorial reading-app-style UI.

## Architecture
Two compose services:
- **api** — FastAPI backend on port 8000 (internal). All API routes are under `/api` prefix.
  Health check at `/health` (root, not prefixed). Swagger docs at `/docs`.
- **web** — Vite + React + TypeScript frontend on port 3000 (the preview port). Proxies
  `/api`, `/health`, `/docs`, `/openapi.json` to the backend.

## Setup
- The app lives in `AI university project/` (subdirectory of repo root).
- Frontend source: `AI university project/frontend/`
- Run: `docker compose -f docker-compose.base44.yml up -d` from that directory.
- Backend: `python:3.12-slim` base, source bind-mounted at `/app`, uvicorn with `--reload`.
- Frontend: `node:22-slim` base, source bind-mounted at `/app`, Vite dev server with HMR.
- SQLite DB created automatically on startup (`data/learning_agent.db`).

## Secrets
- `ANTHROPIC_API_KEY` — required for all core features (research, teaching, grading).
  Delivered via platform env file at `/run/base44/app.env`, loaded as compose `env_file`.
  Do NOT list it under compose `environment:` (overrides the env file with empty value).

## Verifying
- `curl -sf http://localhost:3000/health` → `{"status":"ok"}`
- `curl -sf http://localhost:3000/api/topics` → `[]` (or list of topics)
- Frontend: `http://localhost:3000/` — React app with dashboard
- Swagger UI: `http://localhost:3000/docs`
- External hostname must work: `curl -sf -H "Host: external-preview.example.com" http://localhost:3000/`

## Known quirks
- esbuild (Vite's transformer) had issues parsing template literals with `${}` in JSX
  attributes in SessionView.tsx. Pre-computing URL/className strings as variables before
  the return statement avoids this. Other files with template literals in JSX build fine.
- The backend API is prefixed with `/api` to avoid route conflicts with React Router
  (e.g., `/topics/5` is both a frontend route and an API endpoint without the prefix).
