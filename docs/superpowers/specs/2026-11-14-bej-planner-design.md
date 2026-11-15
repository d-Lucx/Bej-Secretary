# Bej notes-to-daily-plans design

The user has completed discovery and instructed us to get started. Implementation proceeds with the recorded requirements and explicit defaults, without another preference interview.

## Intent and scope

First deliver a usable local daily planner reading the approved Obsidian vault, presenting task candidates with citations, assigning user-selected work/personal tasks to valid time windows, and saving generated Markdown separately. Keep AI optional so planning works without a model. Add local integration settings and approval boundaries for the required Outlook calendar and existing Discord bot.

## Approach

Adapt DomoNote's React/TypeScript stack and Python companion approach. Use a dedicated `bej.html` entry and `bej-companion/` service so inherited marketing, Google Calendar, browser speech, remote fonts, and extension-installation routes are not loaded. The alternative, modifying every inherited route before the first planner works, has a much larger audit surface. A full native rewrite would discard useful upstream work. This architectural choice is the implementer's call in response to the user's instruction to start.

## Local boundaries

- Serve the built Bej UI and API together on `127.0.0.1:8766`. Require a per-process bearer token for all data endpoints. Pass it to the initial browser session in a URL fragment, then remove the fragment and retain it in session storage. No CORS grants; reject foreign Origin and Host headers. The token never appears in HTTP query strings or access logs.
- Read the configured vault only; never follow symlinks/reparse points outside it. Skip application/Git internals as technical metadata. All content folders remain eligible. Limit readable file size and report skipped files.
- Task IDs identify source path, checkbox line, and text. Record a content hash for stale-edit checks. Track heading/fence context so checkbox examples in code/templates remain unscheduled candidates rather than commitments.
- No API modifies source notes in this first increment. Source editing will need an exact, hash-bound preview/approval implementation before it is enabled.
- Save generated plans only under the vault's `Bej Plans` directory. Exclude that generated directory from task re-import. Use unique filenames and atomic writes; do not overwrite an existing file or follow linked plan directories. Plan saves require an explicit click.
- Private state, IDs, plans, and credentials stay outside Git in `.bej-local/`; bot/OAuth secrets use Windows credential storage. No telemetry, remote fonts, or cloud AI.

## Scheduling

Timezone `Asia/Manila` / UTC+8. Work Monday–Friday 08:00–17:00. Personal daily 06:00–22:00, avoiding weekday work hours. Sleep 22:00–06:00. No fixed lunch. No appointments currently. Empty time is not automatically filled.

Users explicitly select candidates and assign work/personal category and duration before scheduling. Unknown durations default to a visible, editable 30-minute estimate; default draft capacity is four hours, editable by the user. These are implementation defaults, not user-confirmed preferences. Overflow remains unscheduled with a reason. Past time on today's date is unavailable. Do not schedule arbitrary notes or long-term goal checkboxes automatically.

The first increment generates a fresh draft; it does not silently move approved Outlook events. Date-specific availability changes must be explicit; full holiday/travel automation is a later increment.

## UI

Calm flat desktop workspace with Today, source-task inbox, and Connections. Show actual local state, source/line, category, duration, unplanned overflow, and the exact saved file. Keyboard accessible labeled inputs, live feedback, readable contrast, reduced motion. Use system fonts and local Lucide SVGs; avoid decorative GPU effects. This is an app, not a marketing page; Design Taste's screen-height/hero/dealt-effect rules do not apply to its workspace.

## Integrations

Ollama: fixed loopback API and small local model only, short context, single request, unload after response. No model pull or cloud fallback on page load. Use AI only for a user-triggered draft explanation, never as the scheduling authority. Show missing model/offline errors without losing the plan.

Discord: outbound reminders to the recorded guild/channel. Token entered locally and stored in Windows credential storage. Sending is never implied by saving a plan. Test/send require explicit actions, suppress mentions, and send only the displayed task/reminder content. Commands, scheduled durable delivery, startup/tray, and native reminders need subsequent increments; do not present them as working before implemented.

Outlook: personal-account Microsoft Graph integration, separate Bej calendar, delegated permissions. App registration/client ID and user sign-in are external setup steps. Use MSAL, not handwritten OAuth. Preview exact calendar changes before each approval. Read synchronization and cached freshness precede event writing. No deletion, attendees, invitations, or unrelated event changes. Do not mark the whole first release complete until Outlook connection and approval-controlled writes are verified.

## Verification and honest delivery

Use filesystem fixtures to prove vault containment, fenced examples, completed tasks, generated-plan exclusion, and read-only scans. Check weekend/work/personal windows, overflow, past time, invalid durations, and repeated task IDs. Exercise API authentication, bad origins, plan output containment, and secret redaction. Run the existing JS suite and the Bej Python suite, a production Bej build, then live loopback smoke checks. Review the rendered UI at desktop and narrow widths. Report external setup and deferred capabilities explicitly.
