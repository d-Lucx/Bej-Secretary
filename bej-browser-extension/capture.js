const ORIGIN = 'http://127.0.0.1:8766';

export function normalizeCapture(input) {
  if (!['selection', 'page'].includes(input.mode)) throw new Error('Choose selected text or visible page text.');
  if (typeof input.title !== 'string' || input.title.length > 500) throw new Error('Title must be at most 500 characters.');
  if (typeof input.url !== 'string' || input.url.length > 4000 || /[\u0000-\u0020\u007f]/.test(input.url)) throw new Error('Use a valid HTTP(S) URL without control characters.');
  let url;
  try { url = new URL(input.url); } catch { throw new Error('Use a valid HTTP(S) URL.'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Only HTTP(S) pages without URL credentials are supported.');
  url.hash = '';
  if (url.href.length > 4000) throw new Error('URL must be at most 4,000 characters.');
  if (typeof input.text !== 'string' || !input.text.trim()) throw new Error('Text is empty. Select text first, or deliberately choose visible page text.');
  return { title: input.title, url: url.href, text: input.text.slice(0, 50000), mode: input.mode, truncated: input.text.length > 50000 };
}

// This function is serialized into the active tab. Keep it self-contained.
export function extractPageText(mode) {
  if (!['http:', 'https:'].includes(location.protocol) || document.contentType === 'application/pdf') throw new Error('This page is unsupported. Paste text in Bej instead.');
  const selection = mode === 'selection' ? window.getSelection() : null;
  if (mode === 'selection' && (!selection || selection.isCollapsed || !selection.rangeCount)) return { title: document.title, url: location.href, text: '' };
  const forbidden = 'script,style,noscript,template,iframe,frame,object,embed,form,input,textarea,select,button,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[hidden],[aria-hidden="true"]';
  const pieces = [];
  let size = 0;
  let visited = 0;
  let clipped = false;
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (++visited > 10000) { clipped = true; break; }
    const parent = node.parentElement;
    if (!parent || parent.closest(forbidden) || parent.isContentEditable) continue;
    let visible = true;
    for (let element = parent; element; element = element.parentElement) {
      const style = getComputedStyle(element);
      if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' || style.contentVisibility === 'hidden' || style.opacity === '0') { visible = false; break; }
    }
    if (!visible || !parent.getClientRects().length) continue;
    let part = '';
    if (selection) {
      for (let i = 0; i < selection.rangeCount; i++) {
        const range = selection.getRangeAt(i);
        if (!range.intersectsNode(node)) continue;
        const start = range.startContainer === node ? range.startOffset : 0;
        const end = range.endContainer === node ? range.endOffset : node.textContent.length;
        part += node.textContent.slice(start, end);
      }
    } else part = node.textContent;
    if (part.trim()) { pieces.push(part.slice(0, 50001 - size)); size += part.length + 1; }
    if (size > 50000) { clipped = true; break; }
  }
  return { title: document.title, url: location.href, text: pieces.join('\n'), truncated: clipped };
}

export async function captureActiveTab(chromeApi, mode) {
  if (!['selection', 'page'].includes(mode)) throw new Error('Unsupported capture mode.');
  const [tab] = await chromeApi.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url) throw new Error('No supported active tab.');
  normalizeCapture({ title: '', url: tab.url, text: 'check', mode });
  const results = await chromeApi.scripting.executeScript({ target: { tabId: tab.id }, world: 'ISOLATED', func: extractPageText, args: [mode] });
  if (!results?.[0]?.result) throw new Error('This page cannot be captured. Paste text in Bej instead.');
  const captured = normalizeCapture({ ...results[0].result, mode });
  return { ...captured, truncated: captured.truncated || !!results[0].result.truncated };
}

export function createCaptureClient(chromeApi, fetcher = fetch) {
  const storage = chromeApi.storage.local;
  let token = '';
  let storageReady = false;
  async function forget() { token = ''; await storage.remove('captureToken'); }
  async function post(route, body, authenticated) {
    if (!storageReady) throw new Error('Trusted local storage is unavailable. Reopen the extension in a supported browser.');
    if (authenticated && !token) throw new Error('Pair this extension with Bej first.');
    let response;
    try {
      response = await fetcher(`${ORIGIN}/extension/web/${route}`, {
        method: 'POST', credentials: 'omit', redirect: 'error', cache: 'no-store',
        headers: { 'Content-Type': 'application/json', ...(authenticated ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify(body), signal: AbortSignal.timeout(15000),
      });
    } catch { throw new Error('Cannot reach local Bej. Start the companion and try again.'); }
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) { if (authenticated) await forget(); throw new Error('Pairing is invalid or revoked. Pair again in Bej.'); }
      if (route === 'pair') throw new Error('Pairing failed. Check the code or generate a fresh code in Bej.');
      throw new Error('Bej rejected this request. Check the fields or request a fresh preview.');
    }
    try { return await response.json(); } catch { throw new Error('Bej returned an invalid response.'); }
  }
  return {
    async initialize() {
      storageReady = false;
      // Fail closed if this browser cannot restrict local storage to trusted contexts.
      await storage.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' });
      token = (await storage.get('captureToken')).captureToken || '';
      storageReady = true;
      return Boolean(token);
    },
    async pair(pairingCode) {
      const result = await post('pair', { pairingCode: pairingCode.trim() }, false);
      if (typeof result.captureToken !== 'string' || !result.captureToken) throw new Error('Bej returned an invalid pairing response.');
      token = result.captureToken;
      await storage.set({ captureToken: token });
    },
    preview(input) { const { truncated, ...capture } = normalizeCapture(input); return post('preview', capture, true); },
    save(previewId) { return post('save', { previewId }, true); },
    forget,
  };
}
