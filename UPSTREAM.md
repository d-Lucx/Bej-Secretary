# DomoNote baseline and Bej adaptation

Project destination: https://github.com/d-Lucx/Bej-Secretary

Upstream reference: https://github.com/darknecrocities/DomoNote

Imported revision: `bf802bc936a8e295d2898951754eb5cf7419175d`.

The complete reference clone remains in `DomoNote/`, excluded from the outer repository. Its source was copied into the workspace root, excluding its nested Git metadata. The root uses the Bej repository as `origin` and DomoNote as `upstream`. This is an initial source import, without upstream Git history in the outer repository. Do not blindly merge unrelated histories; plan future upstream imports explicitly.

The MIT [LICENSE](LICENSE) is preserved. Its copyright and permission notice must accompany copies or substantial portions of the software. Attribution being appreciated is separate from this legal notice requirement.

## Reusable foundation

| Area | Existing source | Bej work still required |
| --- | --- | --- |
| Workspace UI | React 18, TypeScript, Vite, Tailwind | Today/Inbox planning experience, scheduling decisions, capture controls |
| Storage | Dexie / IndexedDB | Vault bridge, durable task identities, backup and migration policy |
| Windows shell | .NET 9 WinForms and WebView2 | Tray lifecycle, sign-in startup, durable Windows reminders |
| Local companion | Python FastAPI on 127.0.0.1:8765 | Authorized filesystem access, stronger endpoint protection, bounded jobs |
| AI | Ollama adapter and setup flow | Small-model profile, no-cloud enforcement, measured extraction quality |
| Capture | Browser audio/screen paths and companion screenshot/transcription endpoints | Consent controls, app exclusions, retention, verified offline transcription |
| Calendar | Upstream optional Google Calendar integration | Bej requires Outlook: read events and create/update approved task blocks. Use a personal Microsoft account and a separate calendar named Bej. Add an Outlook adapter, approval controls, local constraint scheduling, offline calendar state, and explicit sync status. |
| Discord | No Bej reminder adapter identified in initial inspection | Optional outbound reminders and authorized command design |

This is an initial source inspection, not a complete security audit or runtime test.

## Privacy and offline gaps found

- `src/services/audio/transcriber.ts` constructs browser `SpeechRecognition` / `webkitSpeechRecognition`. Do not treat that as proof of offline transcription. The companion has a Faster-Whisper path; its model must be provisioned before offline use.
- `local-companion/main.py` permits `https://domonote.vercel.app` in its CORS allowlist and Ollama startup origins. Windows `StaticServer.cs` also sets that hosted origin. A private Bej build should restrict these paths and protect privileged endpoints; loopback binding alone is insufficient.
- `src/services/updates/update-checker.ts` and `src/services/github/stars.ts` contain external release/star requests. Review invocation and make network access consistent with local-only mode.
- `src/services/calendar/google-calendar.ts` contains external OAuth and Calendar requests. Outlook is the confirmed Bej calendar provider; do not enable Google's integration for Bej. An Outlook adapter is needed. Reading events and creating/updating approved task blocks are authorized; a personal Microsoft account and a separate Bej calendar are selected. Deletion, unrelated-event changes, and invitations are outside that authorization. Disclose Microsoft's network/data boundary and support offline planning from the last synchronized state. No Outlook connection has been configured yet.
- `local-companion/main.py` accepts `OLLAMA_BASE_URL`; Bej local-only mode should reject remote AI destinations and disable Ollama cloud features.
- Upstream AI setup defaults to a larger model than the proposed smoke-test model. Hardware guidance in the README is not a benchmark for this laptop.

## Approaches for the design discussion

1. **Adapt the existing Windows shell and companion — recommended starting point.** Reuse notes, document, AI, and capture work. Add a local scheduler and controlled vault bridge. Tradeoff: audit and simplify inherited network and capture paths.
2. **Build a smaller independent Windows tray app around a new local service.** Gives a narrower runtime and permission surface. Tradeoff: reimplement useful workspace/document features and increase scope. DomoNote remains a reference.

No architecture has been approved yet. The first option fits the requested clone-and-modify direction and should be validated against the first-release priority.

## Changes made in this preparation pass

- Imported the upstream source without executing its setup or build scripts.
- Added the Bej prompt, compatibility report, provenance, and a Bej introduction in README.
- Recorded confirmed scheduling and Discord permissions.
- Downloaded and signature-checked the official Ollama Windows installer; excluded it and the reference clone from Git.
- Connected local Git remotes. No commit or push has been made.

The preparation pass above preceded implementation. Since then, a dedicated Bej entry point and authenticated Python service have been added; see the README and implementation ledger for verified behavior. The legacy DomoNote entry remains upstream reference functionality and has not been certified against all Bej acceptance criteria.
