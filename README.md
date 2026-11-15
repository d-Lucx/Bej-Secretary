# Bej Secretary

A local-first AI assistant for Windows that turns selected Obsidian tasks into daily plans, keeps track of completion, and delivers reminders.

## Features

- **Daily planning:** work/personal schedules, capacity limits, priorities, explicit due dates, and warnings when tasks cannot fit.
- **Obsidian integration:** read Markdown tasks, remember planning choices, and save generated plans separately. Existing task edits require an exact preview and approval.
- **Task progress:** recognize checked source tasks, distinguish missing sources from completed work, and prevent duplicate reminders after ordinary source-line changes.
- **Outlook:** read availability and create/update approved task blocks in a separate **Bej** calendar.
- **Reminders:** persistent desktop and optional Discord alerts, per-plan toggles, quiet hours, and separate delivery history.
- **Manual capture:** microphone and screen recording with pause/resume, elapsed time, review before saving, and optional local transcription.
- **Web notes:** paste text or use the Chrome/Edge extension to capture selected or visible page text. Preview before saving; repeated captures reuse the existing note.
- **Local AI:** optional explanations through Ollama and transcription through a locally installed Whisper model.
- **Windows integration:** tray controls and optional startup at sign-in. Recording always starts manually.

## Get started

For an already configured checkout, double-click **Start-Bej.cmd**. Reopen the authenticated workspace from the tray icon. Stop Bej from the tray or with **Stop-Bej.ps1**.

For a fresh Windows checkout, install Node.js/npm and Python 3.12+ with Python available on PATH, then run:

```powershell
npm ci --ignore-scripts
python -m venv .bej-local/venv
./.bej-local/venv/Scripts/python.exe -m pip install -r bej-companion/requirements.txt
npm run build:bej
```

Create `.bej-local/config.json` with your Obsidian vault path:

```json
{
  "vaultPath": "C:\\path\\to\\Your Vault"
}
```

Launch **Start-Bej.cmd**, then:

1. Choose **Read my vault** and review candidates in **Source inbox**.
2. Select tasks, set type, duration, priority and optional due dates, and choose **Build daily draft**.
3. Save the draft to Obsidian, enable reminders, or review and approve Outlook changes.
4. Use **Review completion** to preview and approve checking off a source task, or check it off directly in Obsidian.

The service runs at `http://127.0.0.1:8766`. Use the launcher or tray to open an authenticated session; the address alone does not grant access. Keep Bej running and the laptop awake for reminders.

### Optional connections and models

- **Ollama:** install Ollama, then run `ollama pull qwen2.5:0.5b`. Planning also works without AI.
- **Local speech:** choose **Prepare local speech model** in Manual capture before using offline transcription.
- **Outlook:** follow [Outlook setup](OUTLOOK_SETUP.md), then connect your personal Microsoft account in **Connections**. A Gmail address used as a Microsoft login is separate from a Google calendar connection.
- **Discord:** follow [Discord setup](DISCORD_SETUP.md). Enter the bot token locally in Connections; never put it in chat, notes or Git.
- **Browser extension:** follow the [Chrome/Edge installation and pairing guide](bej-browser-extension/README.md). Installation is manual; pairing grants capture-only access to the exact approved extension.

## Planning and storage

The current scheduling profile uses **Asia/Manila (UTC+8)**: work Monday–Friday, 8 AM–5 PM; personal time daily, 6 AM–10 PM; quiet hours 10 PM–6 AM. Capacity is adjustable, and date-specific work-day exceptions and unavailable windows support changes of plan.

Tasks due before the plan date are considered first, followed by tasks due that day, then later/undated tasks. Within each group, priority and deadline guide allocation. Unknown deadlines stay unknown; explicit task-line markers `📅 YYYY-MM-DD` and `due:: YYYY-MM-DD` are supported.

| Location | Purpose |
| --- | --- |
| `Bej Plans` in your vault | Generated plan snapshots; never re-imported as source tasks. |
| `Bej Captures/Web` in your vault | Approved webpage notes containing provenance and literal text. Generated captures do not become tasks. |
| `.bej-local/` in the project | Private settings, SQLite state, recordings, models and recoverable backups; excluded from Git. |
| Windows Credential Manager | Microsoft authentication data, Discord token and scoped browser credentials. |

A delivered reminder or elapsed time never counts as task completion. Checking a source task stops obsolete queued alerts; existing published calendar blocks remain unchanged.

## Privacy

Core planning, storage, capture and AI processing stay on the laptop. Models require an initial download; local features then work offline. Outlook and Discord are optional online connections that receive approved task titles/times or reminder details. Source notes, recordings and transcripts are not exported through them.

The companion binds only to loopback. Workspace authentication is separate from the browser extension's limited, revocable credential. There is no automatic recording, browser-history collection, wildcard CORS, cloud AI, or automatic extension installation in the dedicated Bej workspace.

## Build and verify

Use the dedicated Bej build:

```powershell
npm run build:bej
npm test
./.bej-local/venv/Scripts/python.exe -m unittest discover -s bej-companion -p 'test_*.py'
```

The production workspace is generated in `dist-bej/`. The separate browser extension loads directly from `bej-browser-extension/` without a build step. Windows permissions may cause link-creation test fixtures to be skipped.

## Project documentation

- [Assistant requirements](BEJ_ASSISTANT_PROMPT.md)
- [Future improvements and implemented browser capture](FUTURE_IMPROVEMENTS.md)
- [Laptop compatibility and local model guidance](LAPTOP_COMPATIBILITY.md)

Still planned: document-format ingestion, screenshot OCR/SOP generation, richer meeting summaries/action extraction, opt-in webpage task extraction, and more scheduling rules. See the project documentation for the current scope.

## Credits

Bej Secretary is adapted from [DomoNote](https://github.com/darknecrocities/DomoNote) by darknecrocities. The original MIT license and copyright notice are retained in [LICENSE](LICENSE).
