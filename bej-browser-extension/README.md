# Bej Web Notes extension

Manual webpage text capture for the local Bej companion. This is a separate, small extension; do **not** load the inherited `browser-extension` folder or run its installation scripts.

## Install explicitly in Chrome or Edge

1. Start Bej, then open **Web notes** in its sidebar. Pasting text there works without an extension.
2. In Chrome open `chrome://extensions`; in Edge open `edge://extensions`.
3. Enable **Developer mode**, choose **Load unpacked**, and select this checkout's **bej-browser-extension** folder. On the configured laptop: `C:\Yan2_Projects\Bej-Secretary\bej-browser-extension`.
4. Copy the installed extension's **ID** into Bej → Web notes → **Extension ID**.
5. Choose **Generate pairing code**. This immediately revokes any previous browser connection; codes expire after five minutes and are single use.
6. Open the extension popup, expand **Connect to desktop Bej**, paste the code, and choose **Pair with Bej**. Keep codes and credentials out of chat, notes and Git.

No browser is launched and no extension is installed by the companion. Browser policy may prohibit unpacked extensions; use Bej's paste flow if so. Use a current Chrome/Edge version. If the browser asks to allow local network access, the companion address is only `http://127.0.0.1:8766`.

## Save a page excerpt

1. Open an ordinary HTTP(S) page and select the text to keep.
2. Open the extension and choose **Capture selected text**. Alternatively choose **Capture visible page text instead** deliberately.
3. Review/edit the title, source URL and text. Browser pages, PDFs, embedded frames, hidden content and form/editable fields are unsupported. Only loaded text can be captured; page text is not a screenshot or a faithful page archive. Captures are capped at 50,000 characters and clipping is labeled.
4. Choose **Create local save preview**. Review the frozen text and destination, then **Save approved preview**.

Notes are created under **Bej Captures/Web** in your configured vault. Exact normalized title/URL/text/mode repeats reuse a note, including after restart. Changed capture notes are preserved. Captured markup and instructions are literal reference text; they do not become planning tasks. No URL is fetched by the companion, and no capture goes to Discord, Outlook, cloud AI or Ollama.

Review URLs before saving: query parameters can contain private data; fragments are removed. Unsaved text stays only in the open popup and disappears when it closes. A save whose confirmation is interrupted can be checked/retried by capturing the same fields again; deduplication reuses its existing note. If the companion restarted, create a fresh preview.

## Revoke and remove

- **Revoke browser access** in Bej invalidates the scoped token immediately. It also cancels pending pairing codes. Pair again to reconnect.
- **Forget local pairing** removes the browser's local credential only. Use Bej's revoke action to invalidate other copies.
- Disable/remove the extension from the browser extensions page whenever desired.
- The Web notes library can preview deletion of an unchanged generated note and its local record, or removal of a record whose file is already missing. Modified notes must be managed in Obsidian to protect edits. Deletion is logical; SSD storage or external backups may retain copies.

## Permission boundary

The manifest requests `activeTab`, `scripting`, `storage`, and the single loopback companion host. There is no history permission, background worker, automatic content script, meeting capture, microphone, screenshot, general website host permission, native messaging or access to Ollama. Chrome grants [activeTab access only after a user action](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab), and [cross-origin extension fetches require declared host access](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests).

The token is local-only, restricted to trusted extension contexts, and separate from the workspace bearer. Server access requires the exact approved extension Origin and capture-only token. The extension can submit previews and save those previews, but cannot list notes, read the vault, delete captures, change schedules or access other workspace APIs. No wildcard CORS or shell/install endpoints are enabled.

Live installation and pairing are intentionally user actions. Automated verification uses fake browser APIs, isolated loopback fixtures and synthetic content.
