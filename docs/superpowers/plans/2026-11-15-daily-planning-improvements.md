# Daily Planning Improvements Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Independent account display can follow superpowers:dispatching-parallel-agents.

**Goal:** Make daily drafts account for explicit urgency/deadlines and make task completion visible and actionable.

**Architecture:** Extend the existing deterministic planner and private SQLite state. Read completion from source checkboxes, reuse exact source-edit approval, and keep cloud writes separately gated.

**Tech Stack:** Python/FastAPI/SQLite, React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-11-15-daily-planning-improvements.md`

## Global constraints

- Source edits require exact approval and backups; Outlook writes require displayed-batch approval.
- No new automatic capture, external messages, cloud AI or source-note publication.
- Reuse the current checkout and automatically push verified changes; private state stays ignored.

## Review focus

- Old drafts and line-shifted tasks preserve identity without conflating different notes.
- Invalid/ambiguous date markers cannot invent deadlines or crash scanning.
- Checking one task must not classify a missing or renamed task as completed.
- Completion must cancel obsolete alerts without deleting published Outlook events.
- Status refresh must not trigger auth/network or show a different cached Microsoft account.

## Tasks

- [x] Add failing metadata/ranking tests; implement explicit due markers, priority validation, deterministic order and risk messages in a small module and planner.
- [x] Add API/state regressions; persist accepted planning choices atomically with valid drafts, overlay them on source reads, expose source-backed progress and reconcile pending alerts.
- [x] Add Today completion approval and source-inbox priority/deadline fields; preserve source edits and capture behavior. Add connected Microsoft identity display with offline status tests.
- [x] Run regression suites/build, inspect desktop/mobile synthetic flows, request focused independent review, update docs and commit/push verified results.


## Verified result

- Implemented explicit due-marker reading, urgency/deadline ordering, risk messages, and privately remembered choices. Priority/due dates also appear in generated plan notes and local explanation inputs.
- Today reads explicit checked source status, offers the exact completion approval, refreshes progress, and cancels obsolete alerts. Missing sources remain unavailable; completed tasks are removed from new reflows while existing Outlook blocks remain protected. Stale completed drafts cannot be newly published.
- Added stable plan IDs without changing source-edit identities. Existing published/unconfirmed calendar identities override unpublished legacy draft aliases; multiple conflicting owned blocks fail closed. Reminder opt-in follows canonical source identity.
- Connections shows the saved Microsoft sign-in without starting auth/network from status. Deliberate refresh backfills old saved identities; mismatched cached accounts do not switch the connection.
- Independent review found and verified fixes for retained completed-calendar-block conflicts, empty due markers, and unpublished legacy-ID seeding. No remaining material issue in focused re-review.
- Python: 169 tests run, 166 passed, 3 skipped because Windows permissions prohibit link fixtures. JavaScript: 104 tests passed. TypeScript/production build passed.
- Full-app synthetic browser checks passed for priority submission, source-backed progress, completion preselection, preview without writing, approved completion refresh, cleared resolved risks, and connected account display. Desktop and 390px layouts visually inspected using the Design Taste script. No real microphone/screen access or live external writes were used by the fixtures.
- Private SQLite snapshot created before rollout. Updated local service is healthy; saved Microsoft identity and existing draft progress load, Outlook availability refreshes successfully, and pending reminders contain no duplicate keys. No source tasks or Outlook events were edited during rollout validation.

Further roadmap work remains in README.md and FUTURE_IMPROVEMENTS.md; this increment does not claim document ingestion, OCR, meeting action extraction, dependencies/recurrence or browser capture are finished.
