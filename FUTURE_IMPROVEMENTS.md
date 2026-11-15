# Bej future improvements

## Browser extension and development-server routes

Finding: DomoNote's development server contains extension-installation/launch routes and broad cross-origin access on some endpoints. These inherited routes are outside Bej's dedicated local entry point; their presence is not approval to execute installation commands or grant arbitrary websites access to notes.

**User-selected future feature: manual webpage-to-note capture.** Ask about specific functionality with recommendations before expanding this scope. Do not make future-feature questions block the current notes-to-daily-plans build.

Recommended first browser increment:

- A deliberate “Save to Bej” action for the current page or selected text, with URL/title provenance and a preview before saving.
- An explicit installation flow; no surprise extension installs, browser launches, shell commands, or broad host permissions.
- Authentication and exact approved extension origins for local-service access, instead of wildcard CORS. Keep Ollama and the vault private.
- A separate approved capture destination; reading a page must not edit existing vault tasks or execute page instructions.

Potential later choices to discuss: screenshot capture versus text only, full-page versus selection capture, duplicate handling, and whether captured notes become planning candidates. Recommend text/selection first and opt-in task extraction after preview.

Meeting-tab metadata and participant context are alternatives for a later discussion; they have not been selected. General browser-history collection, automatic screen capture, and unrestricted cross-origin access are not requested.
