# Bej Secretary

Private Windows AI assistant project for [d-Lucx/Bej-Secretary](https://github.com/d-Lucx/Bej-Secretary).

This checkout starts from DomoNote. Bej now includes a dedicated local planner, Outlook connection, durable reminder queue, and manual capture workspace. The upstream feature descriptions below do not establish that all Bej requirements have been implemented or verified.

- [Bej Assistant project prompt](BEJ_ASSISTANT_PROMPT.md)
- [Laptop compatibility and Ollama download status](LAPTOP_COMPATIBILITY.md)
- [Upstream baseline and initial gap analysis](UPSTREAM.md)
- [Discord bot and private-channel setup](DISCORD_SETUP.md)
- [Future improvements and browser capture](FUTURE_IMPROVEMENTS.md)
- [Design and current scope](docs/superpowers/specs/2026-11-14-bej-planner-design.md)

## Run the Bej planner

On this laptop, double-click **Start-Bej.cmd**, or run `./Start-Bej.ps1` from PowerShell. Keep its process running while using Bej. It opens an authenticated browser session at `http://127.0.0.1:8766`; opening that address in a new browser session without the launcher does not grant access. Reuse the open tab if Bej is already running. Use the tray icon to reopen an authenticated tab. Quit from the tray, close its console, or run `./Stop-Bej.ps1` to stop the local service. Windows sign-in startup is enabled on this laptop. The tray icon opens Bej, pauses reminders, and quits; recording never starts automatically.

1. Choose **Read my vault**. Reading never changes source notes.
2. Select candidates in **Source inbox**, choose work/personal, and adjust the visible duration estimates (30 minutes initially).
3. Choose the date and task capacity (four hours initially, editable), then **Build daily draft**. Overflow remains unscheduled with a reason. Weekday personal tasks stay outside the 8 AM–5 PM work window; all dates use Manila time.
4. Choose **Save plan to Obsidian** to create a new Markdown file in the vault's separate **Bej Plans** folder. Plans are never imported as new tasks. Repeating save for the same persistent draft does not create another file. Source notes remain untouched.
5. Optionally choose **Explain with local AI**. `qwen2.5:0.5b` is installed and has passed a synthetic-plan smoke test. AI is not the scheduling authority.

Local setup, including the vault path and Discord IDs, is in Git-ignored `.bej-local/config.json`. The **Connections** page can save a Discord token directly into Windows Credential Manager. Token entry does not send a message or enable delivery. The configured bot has passed an explicitly approved generic live delivery test. Do not paste credentials into chat, Obsidian, or Git.

## Setup on another Windows checkout

Install Node and Python 3.12+, then:

```powershell
npm ci --ignore-scripts
python -m venv .bej-local/venv
./.bej-local/venv/Scripts/python.exe -m pip install -r bej-companion/requirements.txt
npm run build:bej
./Start-Bej.ps1
```

Create `.bej-local/config.json` with a `vaultPath` pointing to the approved Obsidian vault. The default is the current user's `Documents/Master Vault`. Optional local AI requires Ollama and `ollama pull qwen2.5:0.5b`. No model is downloaded automatically on app load. The dedicated Bej build has no marketing pages, extension-installation endpoints, remote fonts, analytics, or external asset dependencies.

## Outlook and reminders

Outlook is signed in with the personal Microsoft account and the separate **Bej** calendar has been created/reused. Calendar reads and the saved sign-in were verified after restart. No personal task events have been published during setup.

- In **Connections**, refresh Outlook availability for the plan date, then rebuild the draft to avoid busy events.
- In **Today**, choose **Review Outlook calendar changes** to see the task events Bej proposes creating/updating, then approve the displayed batch. Opening the preview does not publish anything. Bej only creates/updates its owned blocks; no invitations, deletions, or unrelated event edits. External changes are checked again before writes. Cyclic batch moves require separate approvals rather than unapproved temporary moves.
- Use the **Discord reminders** and **Desktop reminders** switches for the displayed plan. On shows its pending count; Off cancels only that plan's pending alerts for that destination. A delivery already in progress may still arrive. Switches reload saved queue state; global delivery pauses are shown separately. Alerts occur at block start and respect 10 PM–6 AM quiet hours. The queue survives restart and expires alerts over 30 minutes late.
- **Reminders** separates active alerts from history, retaining canceled/sent records for review. The same source task has at most one queued alert per day and destination, even after line shifts or rescheduling; sent/uncertain deliveries are not rearmed for that task/day/destination. Source identity uses note, heading and normalized exact title; identical names in different notes/headings remain separate. Repeated instances of the same source task cannot be selected together in one draft. Existing key upgrades keep a private SQLite backup.
- Completion comes from the source checkbox: mark it `[x]` in Obsidian, or choose **Source inbox → Propose task edit → Mark this task complete**, preview, and approve. Inbox selection checkboxes only select tasks for planning. A sent reminder or elapsed time never proves completion. Bej checks for an unchecked source before delivering and rejects stale/completed drafts when enabling reminders. Rescan to update the inbox; historical drafts and delivery records remain. A removed or renamed source stops obsolete alerts without being treated as proof of completion. Bej does not read Discord replies or Outlook attendance as completion signals.
- The laptop must remain awake and running Bej; Discord and Outlook additionally need internet.
- Use **Plans changed? Protect some time** to rearrange flexible local tasks around a new unavailable window. Already-pending per-task reminders follow the changes; canceled reminders stay canceled. Outlook changes still require a new preview/approval.
- **Holiday / no work on this date** is a date-scoped override; personal time remains inside the sleep-protected day.

## Source edits and manual capture

**Source inbox → Propose task edit** creates an exact before/after preview. Only **Approve this source edit** writes the existing checkbox line. Stale approvals are rejected; original bytes are backed up privately. External editors can still race within the final check/replace interval, so avoid simultaneous edits to the same note.

**Manual capture** offers explicit microphone recording or selected-screen video. Capture never starts at sign-in or on an app/calendar event. Stop/pause controls remain visible, sessions are capped at five minutes/45 MiB in the browser, and uploads at 50 MiB. Review before saving. Saved recordings can be played/downloaded and explicitly deleted with their transcript. Retention is **until explicit deletion**, with no automatic purge.

An elapsed **MM:SS** counter shows active recording time for microphone and screen capture. It freezes during pause and after stop, stays beside the unsaved preview, and resets for a new recording. The five-minute session limit still includes paused time.

Microphone recordings can be transcribed using the installed local tiny Whisper model. The local speech test recognized a synthetic sentence in approximately 3.9 seconds, without microphone access or cloud transcription. Screen recording currently has no audio; transcription is offered for microphone recordings. Pin `av==16.0.1`: the latest PyAV release removed an argument Faster-Whisper 1.2.1 requires.

## Current limits and verification

Drafts and reminder states persist in private SQLite; **Open a saved draft** restores one in the UI. Calendar availability is cached, dated, and visibly marked stale offline. Source/recording data, credentials, model caches, and generated plans are excluded from Git.

Still future: manual webpage-to-note capture (selected in FUTURE_IMPROVEMENTS.md), screenshot OCR/SOP generation, document-format ingestion in the dedicated Bej UI, richer meeting summaries/action extraction, and custom travel/overnight availability rules. Routine quiet hours remain fixed at 10 PM–6 AM unless an explicit future notification-exception policy is configured. This is a usable first assistant, not a claim that every roadmap capability is complete.

Verification: `npm test`, `npm run build:bej`, and `./.bej-local/venv/Scripts/python.exe -m unittest discover -s bej-companion -p 'test_*.py'`. Restricted sandboxes may require normal Windows thread/socket access for API tests. Windows link fixtures are skipped where OS permissions forbid creating links.

Bej's app registration/calendar integration does not require paid Azure hosting or Entra premium. Standard Graph APIs are available without an additional API charge within normal usage limits. Other Azure resources or premium products can generate separate charges; this project does not deploy them. See [Microsoft Entra ID Free](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/microsoft-entra-id-free) and [Graph API metering](https://learn.microsoft.com/en-us/graph/metered-api-overview).

## Upstream DomoNote documentation

<div align="center">

<img src="src/assets/official_domonote.png" alt="DomoNote Logo" width="96" />

# DomoNote

**Your Local AI Personal Secretary**

> Capture it. Understand it. Keep it — entirely on your device.

<!-- Status & Quality -->
[![Release](https://img.shields.io/badge/Release-v1.0.2-10b981?style=flat-square&logo=github&logoColor=white)](https://github.com/darknecrocities/DomoNote/releases/latest)
[![License](https://img.shields.io/badge/License-MIT-3b82f6?style=flat-square&logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Privacy](https://img.shields.io/badge/Privacy-100%25_Local-emerald?style=flat-square&logo=shield&logoColor=white)](#-privacy)
[![Tests](https://img.shields.io/badge/Tests-84_Passed-brightgreen?style=flat-square&logo=vitest&logoColor=white)](https://github.com/darknecrocities/DomoNote/actions)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088ff?style=flat-square&logo=githubactions&logoColor=white)](https://github.com/darknecrocities/DomoNote/actions)

<!-- Frontend & Web Core -->
[![React](https://img.shields.io/badge/React-18.3-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178c6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-6.4-646cff?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38bdf8?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Dexie.js](https://img.shields.io/badge/Storage-IndexedDB_(Dexie)-8b5cf6?style=flat-square&logo=databricks&logoColor=white)](https://dexie.org)

<!-- Local AI & Audio Intelligence -->
[![Ollama](https://img.shields.io/badge/AI_Engine-Ollama_Local-black?style=flat-square&logo=ollama&logoColor=white)](https://ollama.com)
[![Models](https://img.shields.io/badge/LLMs-CodeGemma_%7C_Llama_3_%7C_Qwen_2.5-7c3aed?style=flat-square&logo=openai&logoColor=white)](https://ollama.com/library)
[![Speech](https://img.shields.io/badge/Speech-Web_Speech_%26_Audio_API-f59e0b?style=flat-square&logo=webrtc&logoColor=white)](#-meeting-secretary)
[![Translation](https://img.shields.io/badge/Translation-Multilingual_AI_(10+_Langs)-06b6d4?style=flat-square&logo=googletranslate&logoColor=white)](#-features-at-a-glance)

<!-- Desktop Native Apps & Extensions -->
[![Windows](https://img.shields.io/badge/Windows-.NET_9_%7C_WebView2-0078d4?style=flat-square&logo=windows&logoColor=white)](#windows)
[![macOS](https://img.shields.io/badge/macOS-Swift_Native_%7C_Universal-000000?style=flat-square&logo=apple&logoColor=white)](#macos)
[![Linux](https://img.shields.io/badge/Linux-AppImage_%7C_Debian_%7C_Tarball-fcc624?style=flat-square&logo=linux&logoColor=black)](#linux)
[![Chrome Extension](https://img.shields.io/badge/Extension-Chrome_MV3-4285f4?style=flat-square&logo=googlechrome&logoColor=white)](#-chrome-extension)

[**Download App**](#-download-the-app) · [**Clone & Run**](#-clone--run-locally) · [**Deploy Online**](#-deploy-to-vercel) · [**Chrome Extension**](#-chrome-extension)

</div>

---

## What is DomoNote?

DomoNote is a **privacy-first, local AI workspace** for knowledge workers. It captures what happens across meetings, documents, screen operations, and notes — then organizes and synthesizes them using local AI models that run entirely on your device.

**No cloud. No subscriptions. No tracking. Just you and your work.**

---

## ✨ Features at a Glance

| Feature | Description |
|---------|-------------|
| 📝 **Notes** | Markdown editor with autosave, version history, tags |
| 🎙️ **Meeting Secretary** | Live audio recording, transcription, AI synthesis |
| 📄 **Document Intelligence** | PDF viewer, annotations, AI analysis |
| 🖥️ **Operation Capture** | Screen recording → auto-generated SOP manuals |
| 🤖 **AI Workspace** | Multi-context chat with local Ollama models |
| 🔒 **100% Local** | All data stored in your browser's IndexedDB |
| 🌐 **Works Offline** | No internet required after first load |

---

## 📦 Download the App

The easiest way to use DomoNote — no Git or Node required.

### Windows

| Installer | Description |
|-----------|-------------|
| [**DomoNote-Setup-x64.exe**](https://github.com/darknecrocities/DomoNote/releases/latest) | ✅ Recommended — One-click installer with Start Menu & Desktop shortcuts |
| [**DomoNote-Windows-Portable.zip**](https://github.com/darknecrocities/DomoNote/releases/latest) | Portable ZIP — extract and run, no installation |
| [**DomoNote-Setup.bat**](https://github.com/darknecrocities/DomoNote/releases/latest) | Developer setup script (auto-installs Node + Ollama) |

**Steps:**
1. Download `DomoNote-Setup-x64.exe` from the [latest release](https://github.com/darknecrocities/DomoNote/releases/latest)
2. Run the installer — it will create Desktop and Start Menu shortcuts
3. Launch **DomoNote** — it will guide you through the AI setup automatically

### macOS

| Download | Description |
|----------|-------------|
| [**DomoNote-macOS-Universal.dmg**](https://github.com/darknecrocities/DomoNote/releases/latest) | Universal binary (Intel + Apple Silicon) |
| [**DomoNote-macOS-arm64.dmg**](https://github.com/darknecrocities/DomoNote/releases/latest) | Apple Silicon (M1/M2/M3) only |
| [**DomoNote-macOS-x64.dmg**](https://github.com/darknecrocities/DomoNote/releases/latest) | Intel Mac only |

**Steps:**
1. Download the `.dmg` for your Mac
2. Open the `.dmg` and drag **DomoNote** to your Applications folder
3. Launch **DomoNote** — if macOS blocks it, run:
   ```bash
   xattr -cr /Applications/DomoNote.app
   ```
4. DomoNote will automatically detect and set up Ollama on first launch

### Linux

| Package / Installer | Description |
|---------------------|-------------|
| [**DomoNote-Linux-x86_64.AppImage**](https://github.com/darknecrocities/DomoNote/releases/latest) | ✅ Recommended — Standalone universal executable for all distributions |
| [**domonote_1.0.2_amd64.deb**](https://github.com/darknecrocities/DomoNote/releases/latest) | Native Debian / Ubuntu package (`sudo dpkg -i domonote_1.0.2_amd64.deb`) |
| [**DomoNote-Linux-x64.tar.gz**](https://github.com/darknecrocities/DomoNote/releases/latest) | Portable standalone archive with launcher |
| [**DomoNote-Setup.sh**](https://github.com/darknecrocities/DomoNote/releases/latest) | Automated 1-line curl setup script |

**Quick Terminal Install:**
```bash
curl -fsSL https://domonote.vercel.app/downloads/DomoNote-Setup.sh | bash
```

---

## 🤖 Local AI Setup (Ollama)

DomoNote's AI features run entirely on your device using **Ollama**. On first launch, DomoNote will automatically:

1. Check if Ollama is installed and running
2. If not found — guide you through downloading and installing it
3. Download the default AI model (`qwen2.5:3b`, ~2 GB)
4. Mark setup complete — you'll never see the setup screen again

> **No API key. No subscription. No internet required for AI after setup.**

### Manual Ollama Setup (if needed)

If the automatic flow doesn't work, install Ollama manually:

**macOS / Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b
```

**Windows (PowerShell):**
```powershell
# Download from https://ollama.com/download/OllamaSetup.exe
# Then open a new terminal and run:
ollama pull qwen2.5:3b
```

After installing Ollama, open DomoNote → Settings → **Setup / Repair AI** to re-run the setup flow.

### Supported AI Models

DomoNote works with any Ollama model. Recommended models by hardware:

| Hardware | Recommended Model | VRAM / RAM |
|----------|------------------|------------|
| Any (default) | `qwen2.5:3b` | ~4 GB |
| 8 GB RAM | `llama3.2:3b` | ~4 GB |
| 16 GB RAM | `gemma2:9b` | ~8 GB |
| 24+ GB VRAM | `llama3.1:70b` | ~48 GB |

Change the model in **Settings → AI Engine → Models Catalog**.

---

## 🔁 Clone & Run Locally

For developers or anyone who wants to run from source.

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| **Node.js** | 18 or later | [nodejs.org](https://nodejs.org) |
| **npm** | 9 or later | Included with Node |
| **Git** | Any | [git-scm.com](https://git-scm.com) |
| **Ollama** | Latest | [ollama.com](https://ollama.com) |

---

### Option A — Automated Start Script (Recommended)

The start script handles everything: dependency check, Ollama verification, and launching the app.

**macOS / Linux:**
```bash
git clone https://github.com/darknecrocities/DomoNote.git
cd DomoNote
chmod +x start.sh
./start.sh
```

**Windows (Command Prompt):**
```cmd
git clone https://github.com/darknecrocities/DomoNote.git
cd DomoNote
scripts\setup-windows.bat
```

**Cross-platform (npm):**
```bash
git clone https://github.com/darknecrocities/DomoNote.git
cd DomoNote
npm start
```

The script will:
- Verify Node.js and npm versions
- Install dependencies if not present
- Check if Ollama is running and start it if needed
- Open DomoNote at `http://localhost:5176`

---

### Option B — Manual Step-by-Step

```bash
# 1. Clone the repository
git clone https://github.com/darknecrocities/DomoNote.git
cd DomoNote

# 2. Install dependencies
npm install

# 3. Start the development server
npm run dev
```

Open your browser at **[http://localhost:5176](http://localhost:5176)**

> On first launch, DomoNote will detect Ollama and walk you through the AI model setup automatically.

---

### All Available Scripts

```bash
npm run dev           # Start development server (hot reload)
npm run build         # Build for production (outputs to /dist)
npm run preview       # Preview the production build locally
npm run test          # Run unit and integration tests (Vitest)
npm run setup:ollama  # Run the Ollama setup shell script directly
npm start             # Cross-platform: install deps + start dev server
npm run build:windows # Build Windows native installer (.EXE)
```

---

## 🌐 Deploy to Vercel

DomoNote is a fully static Single Page Application — no backend required.

```bash
# 1. Fork or clone the repository to your GitHub account

# 2. Go to vercel.com → New Project → Import your repo

# 3. Vercel settings:
#    Framework Preset: Vite
#    Build Command:    npm run build
#    Output Directory: dist

# 4. Click Deploy
```

When accessed from a local machine, DomoNote seamlessly connects to Ollama running at `http://localhost:11434`. All note-taking, PDF viewing, meetings, and recording features work in the browser regardless of where it's deployed.

> A `vercel.json` is included in the repository for correct SPA routing rewrites.

---

## 🧩 Chrome Extension

Capture Google Meet audio and browser tab audio directly into DomoNote.

**Install from source:**
1. Open Chrome → navigate to `chrome://extensions`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select the `/browser-extension` folder from this repository
5. The DomoNote puzzle-piece icon will appear in your Chrome toolbar

**Usage:**
- Join a Google Meet call
- Click the DomoNote extension icon in the toolbar
- Audio streams directly into your active Meeting Secretary session

> The extension requires DomoNote to be open in another tab.

---

## 🐍 Optional: Local Companion (Advanced)

The Local Companion is a Python FastAPI service that unlocks advanced desktop features:
- 🎙️ **Faster-Whisper** — higher accuracy transcription
- 🖥️ **Desktop screen capture** — captures real desktop windows (not just browser tabs)
- ⚡ **Ollama lifecycle proxy** — auto-starts Ollama service

```bash
# Navigate to the companion directory
cd local-companion

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate.bat     # Windows

# Install Python dependencies
pip install -r requirements.txt

# Start the companion service
uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```

The companion runs at `http://localhost:8765` and is automatically detected by DomoNote.

---

## 🗂️ Project Structure

```
DomoNote/
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── ai-workspace/   # AI chat + context selector
│   │   ├── documents/      # PDF viewer + annotation layer
│   │   ├── layout/         # Sidebar, topbar, app layout
│   │   ├── meetings/       # Audio recorder, transcript
│   │   ├── ollama/         # Ollama setup flow wizard
│   │   ├── operations/     # Screen capture + manual builder
│   │   ├── ui/             # Buttons, modals, empty states
│   │   └── updates/        # Update banner
│   ├── context/            # React context providers (AI, workspace)
│   ├── services/
│   │   ├── ai/             # Ollama API, RAG, model detection, setup
│   │   ├── audio/          # Speech transcriber
│   │   ├── documents/      # PDF/DOCX/PPTX parser
│   │   ├── export/         # JSON, PDF, Markdown export
│   │   └── updates/        # GitHub Releases update checker
│   ├── views/              # Top-level page views
│   ├── db.ts               # Dexie IndexedDB schema
│   ├── types.ts            # TypeScript type definitions
│   └── App.tsx             # Root app component
├── browser-extension/      # Chrome extension source
├── local-companion/        # Python FastAPI companion service
├── scripts/                # Build + setup automation scripts
├── public/                 # Static assets
├── index.html
├── vite.config.ts
├── tailwind.config.js
└── package.json
```

---

## 🔒 Privacy

| Data | Where it lives |
|------|---------------|
| Notes, meetings, documents | Browser IndexedDB — your device only |
| AI prompts & responses | Sent to local Ollama (`localhost:11434`) only |
| Audio recordings | Processed in-browser, stored in IndexedDB |
| Analytics / telemetry | ❌ None — zero third-party tracking |

DomoNote contains **no external analytics, no tracking pixels, no CDN-loaded scripts**. Everything runs from your local files or your self-hosted deployment.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend Framework** | React 18.3 + TypeScript 5.6 |
| **Build & Bundler** | Vite 6.4 (Code splitting & ES modules) |
| **Styling & Design System** | Tailwind CSS 3.4 (Curated monochrome, glassmorphism, responsive) |
| **Local Database & Storage** | Dexie.js (IndexedDB — offline-first, client-only persistence) |
| **Desktop Shell (Windows)** | .NET 9 WinForms + Microsoft.Web.WebView2 + DWM dark mode |
| **Desktop Shell (macOS)** | Swift 5 + WebKit (WKWebView) + NSStatusBar Menu Bar Controller |
| **Desktop Shell (Linux)** | Standalone AppImage, Debian (.deb) package, and portable runner |
| **Browser Extension** | Chrome Manifest V3 (Audio loopback capture & Always-on-top HUD) |
| **Local AI Engine** | Ollama REST API (CodeGemma, Llama 3, Qwen 2.5, Mistral) |
| **Speech & Audio Engine** | Web Speech API, Web Audio API Analyzer, MediaRecorder, Faster-Whisper |
| **Multilingual AI Translation** | Real-time Ollama translation pipeline (10+ languages) |
| **Document Processing** | PDF.js (viewer & text extraction), Mammoth (.docx), JSZip (.pptx) |
| **Export Engines** | jsPDF, HTML2Canvas, standard Markdown, CSV, JSON |
| **Security & Sanitization** | DOMPurify (Strict HTML/Markdown XSS sanitization) |
| **Testing Suite** | Vitest (84 unit and integration tests) |
| **CI / CD Pipeline** | GitHub Actions (automated multi-OS build & release packaging) |

---

## 🐛 Troubleshooting

### "Local AI Offline" on startup

1. Open **Settings → Local AI → Setup / Repair AI**
2. Follow the guided setup wizard
3. Or run manually:
   ```bash
   ollama serve          # Start the Ollama service
   ollama pull qwen2.5:3b  # Download the default model
   ```

### Ollama CORS error (browser can't reach localhost:11434)

```bash
# Set OLLAMA_ORIGINS to allow browser access
OLLAMA_ORIGINS="*" ollama serve

# Or on Windows (PowerShell):
$env:OLLAMA_ORIGINS="*"; ollama serve
```

### macOS: "DomoNote can't be opened because it's from an unidentified developer"

```bash
xattr -cr /Applications/DomoNote.app
```

### Port conflict (5176 already in use)

```bash
# Find what's using the port
lsof -i :5176

# Start dev server on a different port
npm run dev -- --port 3000
```

### PDF not rendering

- Make sure the file is a valid PDF (not password-protected)
- Maximum file size: **80 MB**
- Supported formats: PDF, DOCX, PPTX, TXT, Markdown

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push to your fork: `git push origin feat/your-feature`
5. Open a Pull Request

Please follow the existing code style (TypeScript strict, Tailwind dark/light mode variants on all UI elements).

---

## 📋 Changelog

See [GitHub Releases](https://github.com/darknecrocities/DomoNote/releases) for the full version history.

---

## 📄 License

**MIT License** — see [LICENSE](LICENSE) for details.

Free to use, modify, and distribute. Attribution appreciated but not required.

---

<div align="center">

Made with ❤️ by [darknecrocities](https://github.com/darknecrocities)

**[⭐ Star on GitHub](https://github.com/darknecrocities/DomoNote)** · **[📦 Download Latest](https://github.com/darknecrocities/DomoNote/releases/latest)** · **[🐛 Report a Bug](https://github.com/darknecrocities/DomoNote/issues)**

</div>
