# Manual Webpage Capture Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the companion. Independent extension and workspace UI tasks use superpowers:dispatching-parallel-agents. Request one focused independent review before completion.

**Goal:** Deliver explicit, previewed webpage-to-note capture with a scoped local browser connection.

**Architecture:** A small capture repository owns immutable previews and durable no-overwrite notes. A bridge owns expiring pairing and exact-origin scoped auth. An isolated router integrates those with the existing local boundary. A separate unpacked MV3 popup and React Web notes page use the documented API.

**Tech Stack:** Python/FastAPI/SQLite; vanilla extension JavaScript/HTML/CSS; React/TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-15-webpage-capture.md`

## Constraints and review focus

- Keep workspace bearer, note reads, cloud connectors and Ollama unavailable to the extension.
- No automatic browser installation, page injection, background capture or source-note edits.
- Ensure approved extension Origins cannot use workspace APIs or bypass revocation.
- Freeze actual saved bytes, including provenance; reject stale/modified/link destinations.
- Preserve duplicate behavior across restarts and ambiguous interrupted saves.
- Keep captured task-like instructions literal and outside planning candidates.

## Tasks

- [x] Add failing tests and implement capture persistence, immutable previews, deduplication, safe note saving/deletion and scanner exclusion.
- [x] Add failing pairing/security/API tests; implement project-scoped capture credentials and isolated exact-origin routes with streamed request limits.
- [x] Build the manual MV3 popup, scoped pairing, text extraction and explicit installation guide with fake-boundary tests.
- [x] Build Web notes pairing/paste/preview/library controls using the existing UI system and inspect desktop/mobile synthetic flows.
- [x] Run regressions/build, review the trust boundary, fix findings, update documentation, roll out the companion without installing the extension, and commit/push verified work.


## Verified result

- User confirmed selected text plus optional visible-page text. Implemented a separate manual MV3 popup and Web notes paste/preview/save/library page; no inherited installer or broad CORS route was enabled.
- Capture input is bounded and untrusted. URL fragments are removed, no URL is fetched, HTML/Markdown is fenced literally, generated capture filenames stay out of planning while unrelated notes remain readable, and exact repeated captures reuse the existing file.
- Pairing is one-use/five-minute/five-failure, project scoped, exact extension Origin only, and separate from workspace authentication. Revocation replaces token scope so old previews cannot be saved after re-pairing. Status exposes neither token nor code. Streamed inputs are capped independently of Content-Length.
- Saves reserve durable approved bytes before atomic no-overwrite publication and recover after an interrupted confirmation. Saved rows remove full text; changed notes are preserved. Deletion is previewed and stale checked; missing-file metadata can also be removed.
- Independent review caught pairing after failed trusted storage initialization and missing-file metadata deletion being disabled. Both are fixed; focused re-review reported no remaining material issue.
- Python: 188 tests run, 185 passed, 3 Windows link-permission skips. JavaScript: 112 passed. TypeScript/production build passed.
- Synthetic full-app desktop/390px checks passed for literal text, immutable preview/edit invalidation, save, duplicate reuse, exact deletion, pairing code display and revocation. Popup checks used fake Chrome APIs and synthetic DOM content: no read on open, explicit selection action, hidden/form omission, inert preview, edit invalidation, save-only-preview-ID, and token-only trusted local storage. The extension was not installed in a user browser.
- Private state backed up and companion restarted. Live Web notes status/library require workspace authentication, foreign Origin is rejected without wildcard CORS, and the capture library is empty. Rollout did not pair an extension, save personal page text, edit source notes or change calendar events.

Manual installation/pairing remains an intentional user step; see bej-browser-extension/README.md. Rich formatting, PDFs, screenshots/OCR, browser history, meeting metadata and task extraction remain outside this increment.
