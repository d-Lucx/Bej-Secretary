# Bej Planner Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. The user has instructed us to start; use the current suitable checkout and implement natively.

**Goal:** Make an authenticated local Obsidian-to-daily-plan workspace usable on this laptop.

**Architecture:** Dedicated React entry plus a same-origin loopback Python service. Pure filesystem/parser/scheduler functions are separated from HTTP and optional external integrations.

**Tech Stack:** Existing React 18, TypeScript, Vite, Lucide; Python 3.12, FastAPI, Uvicorn, requests, Windows credential storage.

**Spec:** `docs/superpowers/specs/2026-11-14-bej-planner-design.md`

## Global constraints

- Work: Monday–Friday 08:00–17:00; personal daily 06:00–22:00; sleep 22:00–06:00; UTC+8.
- No source-note writes. Explicit save only into `Bej Plans`, with generated files excluded from task discovery.
- No cloud AI, telemetry, remote assets, secrets in Git, or implicit external sends.
- Per-process bearer authentication; same-origin loopback API only.
- Report integrations as pending until actually implemented and verified.

## Review focus

- Symlink/reparse paths must not escape the vault or plan directory.
- Fenced examples, completed checkboxes, and generated plans must not become open task candidates.
- Weekend work, overnight personal work, past time, duplicates, and capacity overflow must not create invalid blocks.
- Foreign origins and unauthenticated API requests must never return private data.
- Offline AI or integration errors must preserve the current draft and never imply delivery/sync.

## Task 1: Vault and scheduler core

Files: `bej-companion/planner.py`, `bej-companion/test_planner.py`.

Interfaces: `scan_vault(root: Path) -> dict`, `make_plan(tasks: list[dict], day: str, capacity: int, now: datetime | None) -> dict`, `save_plan(root: Path, plan: dict) -> Path`.

- [ ] Write failing real-filesystem and literal-time fixtures covering the review focus.
- [ ] Run `python -m unittest discover -s bej-companion -p test_planner.py`; observe missing behavior.
- [ ] Implement parsing, explicit task selection, bounded scheduling, and safe unique plan saves.
- [ ] Rerun the same tests until green.

## Task 2: Authenticated local runtime

Files: `bej-companion/server.py`, `bej-companion/test_server.py`, `bej-companion/requirements.txt`, `Start-Bej.ps1`.

Consumes Task 1 interfaces. Produces authenticated `/api/status`, `/api/tasks`, `/api/plan`, `/api/plans/save`, and optional local AI endpoint.

- [ ] Write API tests for missing auth, foreign origins, wrong hosts, invalid scheduling input, and source-ID validation.
- [ ] Run tests before endpoint implementation, implement the minimal service and launcher, rerun.
- [ ] Bind loopback, serve only the built Bej UI, persist only local configuration, and keep errors free of secrets.

## Task 3: Daily planning UI

Files: `bej.html`, `vite.bej.config.ts`, `src/bej/main.tsx`, `src/bej/style.css`, `package.json`.

Consumes Task 2 JSON API. Show candidates, category/duration choices, editable capacity, draft timeline, overflow, source citations, and explicit Markdown save.

- [ ] Implement labeled keyboard-accessible interactions and preserve drafts on request errors.
- [ ] Build using `npm run build:bej`; verify offline local assets and mobile layout.
- [ ] Show integrations honestly as pending; no fake connection/success controls.

## Task 4: Setup and local smoke verification

Files: `README.md`, `BEJ_ASSISTANT_PROMPT.md`, `docs/superpowers/plans/2026-11-14-bej-progress.md`.

- [ ] Install dependencies, run Python suite and existing JS suite, build Bej, and exercise live loopback endpoints.
- [ ] Verify the real vault scan is read-only; do not generate a personal plan without explicit task selection.
- [ ] Record actual results, launch instructions, known limitations, and subsequent Outlook/Discord/startup increments.
- [ ] Review implementation against privacy, schedule, approval, and user-experience requirements before reporting results.
