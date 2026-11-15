# Connections, reminders, and remaining assistant work

User explicitly authorized automatic pushes and ordered Outlook sync and Discord reminders first, followed by the remaining project tasks. Use the current feature branch; push verified checkpoints automatically. No further preference interview is needed. Account sign-in and private local token entry are the only external setup gates currently identified.

## Implementation decisions

- Keep all private state in a local SQLite database; persist plans, reminder delivery states, settings, and audit events across restarts. No personal state enters Git.
- Outlook: MSAL public-client/device sign-in for a personal account, Windows-protected token cache, separate Bej calendar, cached busy periods, exact expiring publication preview, ETag checks, stable transaction identifiers, no attendees/deletion/unrelated writes. Workstation needs the user's app registration client ID and sign-in.
- Discord: fixed configured server/channel, Windows-protected bot token, verify destination, suppress mentions/embeds, deterministic message nonces, durable queue, bounded retry/rate-limit handling, no blind retry after uncertain delivery. Routine reminders respect 22:00–06:00 quiet hours and expire rather than flooding after sleep/restart.
- A saved local draft does not implicitly authorize external calendar writes or reminder activation. Expose explicit preview/approve and arm controls.
- Then add source-task edit previews with stale-source checks/backups, date-scoped availability exceptions, desktop reminders, startup/tray, and manual capture/retention. Browser webpage capture remains the selected future improvement and is not silently enabled.

## Task sequence and checks

1. Implement and unit-test Outlook and Discord transports independently with fake HTTP/credential boundaries; no synthetic external writes. Independently implement task-edit approvals. Root owns shared state/server/UI.
2. Test and implement SQLite persistence and reminder lifecycle, including duplicate arm, recovery from interrupted send, expired tasks, quiet hours, retries, and cancellation. Worker never reads unapproved source content to send.
3. Wire authenticated API and connection UI; preserve current planner behavior. Add Outlook busy-window avoidance and preview publication; add reminder dashboard/arming/status.
4. Run all Python/JS tests, production build, live read-only account checks, and explicit live generic Discord test once credentials are available. Complete user-driven Outlook sign-in and verify calendar reads before any approved task publication.
5. Commit/push verified connector checkpoint, then continue with remaining tasks and update this ledger. Stop only for required external user actions after completing independent work.

## Progress

- Initial planner branch pushed successfully.
- Client-ID guide written; user asked to enter Discord token locally and supply nonsecret Microsoft client ID.
- Outlook adapter, Discord transport, and source-edit module delegated with disjoint ownership under Superpowers' parallel-work skill.
- Shared persistence, queue, API, and UI in progress.

## Verified checkpoint — November 15, 2026

- Outlook: personal app registration configured locally; device-code consent completed by the user; separate Bej calendar created/reused; real availability sync returned zero busy appointments. A restart preserved the Microsoft cache and a subsequent sync succeeded. No personal task events were published.
- Discord: stored bot credential and exact destination validated. User explicitly approved one generic connection message; it was delivered. Persistent reminder queue and per-plan arming are implemented; no personal reminders were armed by setup.
- Durable local drafts, history/restoration, saved Markdown paths, settings, audit records, per-task reminder consent, quiet hours, missed/uncertain states, source-current checks, and safe rearming implemented.
- Source edit previews are exact, expiring, and single-use, with full-file stale checks and private backups. No real vault task edits were made by verification.
- Windows native notification command completed successfully. Windows sign-in startup enabled; tray opens authenticated workspace, pauses reminders, and quits. Capture stays off at sign-in.
- Manual microphone and selected-screen recording, pause/stop, preview/save/play/download/delete, bounded private uploads, retained-until-explicit-delete storage, and local microphone transcription implemented. Synthetic speech was transcribed exactly in approximately 3.9 seconds; no microphone was accessed. Pinned PyAV16.0.1 after reproducing incompatibility between Faster-Whisper1.2.1 and latest PyAV19.
- Date-scoped work-day-off override and explicit unavailable-window reflow rearrange flexible local tasks; fixed calendar events/source notes remain protected, and Outlook changes need a new approval.
- Independent review found calendar ambiguous-create recovery, reminder reactivation, multi-task calendar ordering, and canceled-reminder reflow issues. Regressions/fixes preserve reserved transaction identity, owned-event versions, safe dependency order/partial retries, and per-task opt-in. Cyclic moves are refused rather than using unapproved temporary events.
- Final Python suite: 136 tests run, 133 passed, 3 skipped because Windows host permissions forbid link creation. Existing JS suite: 102 passed. TypeScript/production build passed. Connected desktop UI visually inspected using the Design Taste headless script; fixed-sidebar stitching artifact is known from the earlier verification and not an app-layout issue.
- Credentials, Microsoft cache, client/server/channel identifiers, captures, transcripts, backups, SQLite, installed models, screenshots, and generated builds remain outside Git. Original source notices preserved.

The account-side gates are resolved. Future enhancements remain documented in README/FUTURE_IMPROVEMENTS.md; the checkpoint does not claim that every advanced roadmap feature is implemented.

## Reminder controls and duplicate diagnosis — November 15, 2026

- Local inspection found pending alerts paired with canceled reschedule history, with no duplicate pending task/destination pairs and no exact duplicate source titles. Active alerts and history now have separate views.
- Per-plan Discord/desktop switches load persisted pending counts and cancel only that plan/destination when switched off. Global delivery pauses remain separate; already in-flight delivery cannot be recalled.
- Reminder identity now uses source note, heading and normalized exact title rather than source line. A private SQLite snapshot precedes legacy-key migration; superseded pending duplicates are canceled with history preserved. Identical titles in different notes/headings remain separate tasks.
- Sent, sending and uncertain deliveries block rearming the same source task/day/destination after rescheduling. Duplicate selections of the same source task are rejected, and enabling stale/completed drafts requires a rescan/rebuild.
- Completion is the checked source checkbox, through Obsidian or an exact approved source edit. Inbox selection, a reminder receipt, elapsed time, Discord replies and calendar blocks are not completion signals. Source validation runs immediately before delivery; removed/changed sources cancel obsolete alerts without asserting completion.
- Independent review caught delivery still relying on line IDs; payload migration and delivery validation now share the canonical source identity. Regression covers unchanged task after line insertion and suppression after checking it off.
- Verification: 143 Python tests run (140 passed, 3 Windows link-permission skips), 102 JS tests passed, TypeScript/production build passed. Synthetic browser interaction checks passed for saved switch state, on/off, remount restoration, and preview without publishing. Desktop and narrow layouts inspected with the Design Taste screenshot script. No live calendar publication or test message was used for these checks.

## Outlook long-title preview correction — November 15, 2026

- A valid local task with a 310-character title was rejected by the adapter's 255-character calendar-title guard. Preview now shortens only the proposed calendar title with an ellipsis and labels the change explicitly; full local tasks and source notes remain unchanged. Approval publishes exactly the displayed title.
- Presentation metadata stays outside the creation-recovery snapshot so an uncertain creation can still be reconciled without a duplicate POST.
- Added regressions for a long title, the 255-character boundary, explicit approval using the displayed title, unchanged source data, and uncertain-creation recovery. Full Python suite: 146 run, 143 passed, 3 Windows link-permission skips. TypeScript/production build passed.
- Live read-only verification: November 16 availability refreshed successfully with zero busy periods; the existing eight-block draft preview returned success, with one shortened calendar title. No calendar events were published.
