# Manual webpage-to-note capture

Implement the first browser increment selected in FUTURE_IMPROVEMENTS.md. Use a new isolated Chromium Manifest V3 extension, not DomoNote's meeting extension or installation routes. Reuse the local companion and React workspace.

## User flow

Install the unpacked extension manually in Chrome/Edge. Copy its extension ID into Bej's Web notes page, generate an expiring one-use pairing code, and paste that code into the extension. The code authorizes only this exact extension origin and a capture-only credential. Revoke/re-pair from Bej. No automatic installation, history monitoring, background injection, recording, or broad website host permissions.

Capture selected text by default; optionally capture the loaded page's visible text after a deliberate action. Show editable title/HTTP(S) URL/text before requesting a frozen local preview. Save only the approved preview. Offer the same paste/preview/save flow inside Bej without an extension. Explain unsupported browser-internal pages/PDFs and clipped text; no silent selection-to-full-page fallback.

The preview displays the fixed destination `Bej Captures/Web` in the configured vault. Saving is approval to create a new note there. Capture notes contain provenance and literal text, not executable HTML or schedulable checkboxes. Exclude generated captures from source-task scanning; task extraction, screenshots, meeting metadata, and history access remain future choices.

## Boundaries

- Manifest permissions: activeTab, scripting, storage; host access only `http://127.0.0.1:8766/*`. No access to Ollama, vault reads, workspace API, Discord or Outlook. No background/content scripts or externally connectable messages.
- The workspace bearer never enters the extension. Pairing codes expire after five minutes and allow at most five failures; capture credentials are project-scoped and stored in Windows Credential Manager and extension local-only trusted-context storage. Captured text is not retained in browser storage.
- Only the exact paired/pending extension origin may reach three POST-only `/extension/web/` routes. Exact CORS, bounded request streaming, exact Host, scoped authorization and revocation are checked server-side. Ordinary web origins and extension access to `/api/` remain rejected. No wildcard CORS or inherited install/shell endpoints.
- Maximum 50,000 text characters, 500 title characters and 4,000 URL characters. HTTP(S) URL only, no userinfo/control characters; remove fragments, never fetch the supplied URL. Treat every page field as data. Freeze a 15-minute preview per requesting scope; save ignores no client-supplied replacement content because it accepts only previewId.
- Deduplicate exact normalized title/URL/text/mode. Repeated saves/restarts reuse the existing note. Use a persistent save reservation, atomic no-overwrite file publication, path containment/link checks and stale checks. Never edit existing source notes or overwrite modified captures.
- Desktop library lists saved metadata and can preview/approve deletion of an unchanged generated capture note plus its local record. Changed notes require manual handling in Obsidian. Retention is until explicit deletion; no remote assets or note contents are fetched/sent externally.

## API contract

Capture input: `{title,url,text,mode}` where mode is `selection`, `page` or `paste`.

Preview response: `{previewId,expiresAt,title,url,text,mode,destination,duplicate,existingPath?,warning?}`. Expiry fields are ISO timestamps. Save request `{previewId}`; response `{path,duplicate}` with a vault-relative path. Generated capture filenames are excluded precisely; unrelated existing notes in the same folder remain in source scope.

Workspace routes: GET `/api/web/status` → `{extensionId,paired,pairingExpiresAt?,destination}`; POST `/api/web/pairing` `{extensionId}` → `{pairingCode,expiresAt}`; POST `/api/web/revoke` `{}`; POST `/api/web/preview`, `/api/web/save`; GET `/api/web/captures` → `{captures:[{id,title,url,mode,path,createdAt,missing,modified}]}`; POST `/api/web/delete-preview` `{captureId}` → `{previewId,title,path}`; POST `/api/web/delete` `{previewId}`.

Extension routes: POST `/extension/web/pair` `{pairingCode}` → `{captureToken}`; POST `/extension/web/preview` with capture input; POST `/extension/web/save` `{previewId}`. Non-pair requests use `Authorization: Bearer <captureToken>` and exact extension Origin. These routes expose no library reads, deletions or general workspace actions.

## Validation

Test exact-origin CORS/auth isolation, credential expiry/reuse/revocation, streamed oversize requests, missing/foreign Origins, immutable previews, literal untrusted content, duplicates after restart, save recovery, link/path/collision refusal, changed-note protection and capture exclusion from planning. Test popup capture actions with fake Chrome APIs, manifest restrictions, and synthetic desktop/mobile flows. Do not install an extension or save personal page content without the user's explicit action.
