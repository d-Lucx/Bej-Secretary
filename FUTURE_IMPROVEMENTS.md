# Bej future improvements

## Browser extension and development-server routes

Finding: DomoNote's development server contains extension-installation/launch routes and broad cross-origin access on some endpoints. These inherited routes are outside Bej's dedicated local entry point; their presence is not approval to execute installation commands or grant arbitrary websites access to notes.

**User-selected future feature: manual webpage-to-note capture.** Ask about specific functionality with recommendations before expanding this scope. Do not make future-feature questions block the current notes-to-daily-plans build.

The first browser increment is now implemented:

- **Web notes** in Bej supports manual paste → frozen preview → save, without an extension.
- The separate **bej-browser-extension** popup captures selected text by default or loaded visible page text by a separate action. Title, URL and literal text are reviewed before saving. There is no selection-to-page fallback.
- [Explicit Chrome/Edge installation and pairing](bej-browser-extension/README.md): no surprise extension installs, browser launches, shell commands or general website host permissions. The inherited DomoNote extension remains separate.
- A one-use five-minute pairing code grants only capture-preview/save access for the exact approved extension origin. The token is separate from the workspace bearer, persists locally, and can be revoked. No wildcard CORS, vault reads, cloud connector access or Ollama access is granted.
- Saving explicitly approves a new note under **Bej Captures/Web**. Generated capture filenames are excluded from task scanning; other user notes remain readable. HTML/Markdown instructions are stored as literal text rather than becoming tasks or remote assets.
- Exact normalized title/URL/text/mode duplicates reuse the existing note across restarts. Interrupted saves retain a recoverable reservation; existing or edited notes are never overwritten.
- The library supports previewed deletion of unchanged generated notes/local records and removal of records whose file is missing. Modified notes remain protected and must be managed in Obsidian.

Confirmed choice: selected text plus optional visible-page text, with no automatic task extraction. Current limits are 50,000 text characters, 500 title characters and 4,000 URL characters; page-complexity clipping is labeled. Browser pages, PDFs, iframes, hidden/form/editable text are unsupported. No source URL is fetched by the companion. Capture notes are retained until explicit deletion; unsaved browser text lasts only while its popup remains open.

Potential later choices to discuss: screenshots/OCR, richer page formatting/PDF capture, and whether captured notes become planning candidates. Recommend opt-in task extraction with its own preview, not automatic import of page checkboxes. Live extension installation/pairing is a manual user step; automated tests use fake Chrome APIs and synthetic content.

Meeting-tab metadata and participant context are alternatives for a later discussion; they have not been selected. General browser-history collection, automatic screen capture, and unrestricted cross-origin access are not requested.
