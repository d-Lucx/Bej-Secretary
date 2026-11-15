# Daily planning improvements

Continue the approved local-first assistant work, prioritizing notes-to-daily-plans and keeping existing source/calendar approvals. Reuse the Python/SQLite companion and React app; no new models or services.

## Behavior

- Selected candidates have an editable priority (urgent/high/normal/low), optional due date, type and duration. Read only explicit task-line due markers (`📅 YYYY-MM-DD` or `due:: YYYY-MM-DD`); ambiguous/invalid markers stay unknown and show a warning. Never infer dates from prose or turn every candidate into a commitment.
- Order allocation by overdue tasks, then tasks due on the selected day, then remaining tasks. Within those groups use explicit priority, then earliest known deadline, then selection order. Capacity, busy events, work/personal windows and sleep protection remain authoritative. Show deadline risks for overdue tasks and due tasks that do not fit. A day-only deadline is not a known time-of-day deadline.
- Remember accepted type/duration/priority/deadline choices privately when a valid draft is built, keyed by existing canonical source identity. Preserve them across line shifts/restarts without modifying source notes. Existing drafts remain history.
- Today shows source-backed completion status. Only an explicit checked source checkbox means completed; missing/renamed sources are unavailable, not done. Completion opens the existing exact source-edit approval with completion selected; no direct checkbox writes. Rescanning/progress checks cancel queued alerts for no-longer-open tasks. Already-published calendar blocks are retained; no deletion authority is added.
- Show the connected Microsoft sign-in address in Connections with a clear distinction between a Microsoft account using a Gmail login and a Google calendar connection. Reading status must not start authentication or network requests, and credentials remain private.

## Implementation choices

Use deterministic ordering and source-backed progress rather than AI guesses or an independent local completion ledger. Parse explicit dates in a small planning metadata module, persist choices alongside SQLite plans, and expose one progress snapshot per displayed plan. Full cross-file task linking, recurrence/dependencies, automatic calendar writes, broader ingestion/OCR and browser extension capture remain separate roadmap work.

## Validation

Cover deadlines/order/overflow, malformed/ambiguous dates, persisted preferences after line shifts and restart, source-read-only behavior, checked versus missing sources, prompt-injection text staying inert, approval-backed completion, immediate alert cancellation, and account status without auth/network. Inspect synthetic desktop/mobile flows and run the existing regression suites/build. Do not use personal data as committed fixtures or send live messages/calendar writes for validation.
