# Implementation ledger — plan: 2026-11-14-bej-planner.md

User instructed us to get started after completing requirements. Working in the existing checkout; no new worktree requested. Native implementation. Architecture and defaults are documented in the design.

Interfaces reviewed: core functions return JSON-serializable task/plan dictionaries consumed by FastAPI and the React workspace. Real source text stays out of committed fixtures and logs.

## Task 1: complete

Added read-only checkbox discovery, source references/hashes, fenced-example filtering, generated-plan exclusion, explicit work/personal scheduling, capacity/overflow, and unique atomic plan saves. Initial tests failed because the core module did not exist; implementation made them pass. Windows sandbox prohibits hard links, so atomic publication uses Windows no-overwrite rename and hard links on other platforms. A symlink fixture is skipped when Windows developer-mode privileges are unavailable.

## Task 2: complete

Added same-origin loopback service, per-process authentication, host/origin validation, strict input handling without credential echo, stale-source checks, idempotent session saves, and local AI without environment proxies/redirects. API tests initially failed on missing service, then passed. Restricted sandbox stalled the test client's worker thread; the same tests pass in normal Windows execution. No broad CORS or inherited extension-installation routes are loaded.

## Task 3: complete

Dedicated Bej build and React planner use local assets only. Source inbox supports explicit selection, category/duration estimates, search, and warnings. Today shows draft times, overflow, source links, explicit save, and optional local explanation. Connections clearly labels unfinished integrations. Default capacity is an editable four hours; no source edits or automatic task acceptance.

## Task 4: complete for this increment

- `npm test -- --reporter=dot`: 12 files / 102 tests passed. Existing offline-fallback stderr and PDF.js Node warning are from upstream tests. Added a separate Vitest config so the ignored reference clone is not tested twice and upstream development middleware is not loaded by tests.
- `python -m unittest discover -s bej-companion -p 'test_*.py'`: 15 tests run, 14 passed, 1 skipped (Windows symlink creation permission); no failures.
- `npm run build:bej`: TypeScript and production build passed. Approximately 169 kB JS and 11 kB CSS before gzip; no public installers or remote fonts bundled.
- Desktop (1440) and narrow (390) screenshots inspected via Design Taste's headless screenshot script. The stitched desktop image initially omitted part of the fixed sidebar; a single 1440x1200 viewport confirmed the sidebar renders correctly. Full marketing-page gate is not applicable to this app workspace.
- Independent code review found two P2 issues: configured-vault links were hardcoded, and scan warning details were discarded. Both fixed and rechecked with no remaining important findings. Added credential-redaction and skipped-file reporting regressions.
- Real vault: 17 notes / 66 candidates / 0 warnings; SHA-256 hashes unchanged before and after scan. No personal plan written by automated tests.
- Live synthetic fixture: status HTTP200, draft created, Markdown plan saved in fixture only, local AI HTTP200 in approximately 3.8 seconds. Model `qwen2.5:0.5b` downloaded successfully and requested to unload after the response.
- Production local service launched, workspace HTTP200, CSP present, unauthenticated vault request rejected with HTTP401. No token, note content, or runtime state committed. No Discord or Outlook messages/events sent.

## Remaining project work

Outlook authentication and approved calendar writes; scheduled Discord and native reminders; source-edit previews/approval; durable plan state/rescheduling; explicit holiday exceptions; startup/tray; manual meeting/screen capture and retention. Manual webpage-to-note capture is the selected future browser improvement. This ledger marks the local planning increment complete, not the entire assistant.
