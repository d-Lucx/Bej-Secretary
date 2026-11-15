import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
// The extension is deliberately plain JS so Chrome can load it without a build.
// @ts-ignore
import { createCaptureClient, captureActiveTab, normalizeCapture, extractPageText } from '../bej-browser-extension/capture.js';
// @ts-ignore
import { initializePopup } from '../bej-browser-extension/popup.js';

describe('isolated web capture extension', () => {
  it('refuses pairing and credential persistence if trusted storage initialization fails', async () => {
    const storage = { setAccessLevel: vi.fn(async () => { throw new Error('unsupported'); }), get: vi.fn(), set: vi.fn(), remove: vi.fn() };
    const fetcher = vi.fn();
    const client = createCaptureClient({ storage: { local: storage } }, fetcher);
    await expect(client.initialize()).rejects.toThrow();
    await expect(client.pair('code')).rejects.toThrow(/storage/i);
    expect(fetcher).not.toHaveBeenCalled();
    expect(storage.set).not.toHaveBeenCalled();
  });
  it('has only deliberate capture permissions and the fixed companion host', () => {
    const manifest = JSON.parse(readFileSync('bej-browser-extension/manifest.json', 'utf8'));
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.permissions).toEqual(['activeTab', 'scripting', 'storage']);
    expect(manifest.host_permissions).toEqual(['http://127.0.0.1:8766/*']);
    for (const key of ['background', 'content_scripts', 'externally_connectable', 'optional_permissions']) expect(manifest[key]).toBeUndefined();
  });

  it('clips text explicitly and strips fragments while rejecting unsafe URLs', () => {
    expect(normalizeCapture({ title: 't', url: 'https://example.test/a#secret', text: 'x'.repeat(50001), mode: 'selection' })).toMatchObject({ url: 'https://example.test/a', text: 'x'.repeat(50000), truncated: true });
    for (const url of ['chrome://settings', 'file:///a', 'javascript:alert(1)', 'https://u:p@example.test', 'https://example.test/\nsecret']) {
      expect(() => normalizeCapture({ title: 't', url, text: 'text', mode: 'page' })).toThrow();
    }
    expect(() => normalizeCapture({ title: 't'.repeat(501), url: 'https://example.test', text: 'text', mode: 'selection' })).toThrow();
    expect(() => normalizeCapture({ title: 't', url: 'https://example.test', text: ' ', mode: 'selection' })).toThrow(/select|empty/i);
  });

  it('injects only after explicit capture and never falls back from empty selection', async () => {
    const chrome = { tabs: { query: vi.fn(async () => [{ id: 7, url: 'https://example.test/#x' }]) }, scripting: { executeScript: vi.fn(async () => [{ result: { title: 'Title', url: 'https://example.test/#x', text: '' } }]) } };
    await expect(captureActiveTab(chrome, 'selection')).rejects.toThrow(/select|empty/i);
    expect(chrome.scripting.executeScript).toHaveBeenCalledTimes(1);
    expect(chrome.scripting.executeScript.mock.calls[0][0]).toMatchObject({ target: { tabId: 7 }, world: 'ISOLATED', args: ['selection'] });
    chrome.tabs.query.mockResolvedValue([{ id: 7, url: 'chrome://settings' }]);
    await expect(captureActiveTab(chrome, 'page')).rejects.toThrow();
    expect(chrome.scripting.executeScript).toHaveBeenCalledTimes(1);
  });

  it('pairs and sends only scoped fixed-loopback POSTs; stores only a trusted local token', async () => {
    const values: Record<string, string> = {};
    const storage = { setAccessLevel: vi.fn(async () => {}), get: vi.fn(async () => values), set: vi.fn(async (v) => Object.assign(values, v)), remove: vi.fn(async () => { delete values.captureToken; }) };
    const fetcher = vi.fn(async () => ({ ok: true, json: async () => ({ captureToken: 'scoped-secret' }) }));
    const client = createCaptureClient({ storage: { local: storage } }, fetcher);
    await client.initialize();
    await client.pair('one-use');
    fetcher.mockResolvedValue({ ok: true, json: async () => ({ previewId: 'frozen' }) });
    await client.preview({ title: 't', url: 'https://example.test', text: 'literal', mode: 'page' });
    await client.save('frozen');
    expect(storage.setAccessLevel).toHaveBeenCalledWith({ accessLevel: 'TRUSTED_CONTEXTS' });
    expect(values).toEqual({ captureToken: 'scoped-secret' });
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['http://127.0.0.1:8766/extension/web/pair', 'http://127.0.0.1:8766/extension/web/preview', 'http://127.0.0.1:8766/extension/web/save']);
    expect(fetcher.mock.calls[0][1].headers).toEqual({ 'Content-Type': 'application/json' });
    expect(fetcher.mock.calls[2][1]).toMatchObject({ method: 'POST', credentials: 'omit', redirect: 'error', headers: { Authorization: 'Bearer scoped-secret' }, body: JSON.stringify({ previewId: 'frozen' }) });
    expect(fetcher.mock.calls.every(([, options]) => !('Origin' in options.headers))).toBe(true);
    await client.forget();
    await expect(client.save('frozen')).rejects.toThrow(/pair/i);
  });

  it('does not echo server error bodies or credentials', async () => {
    const storage = { setAccessLevel: async () => {}, get: async () => ({ captureToken: 'secret' }), remove: vi.fn(async () => {}) };
    const client = createCaptureClient({ storage: { local: storage } }, async () => ({ ok: false, status: 401, json: async () => ({ detail: 'secret' }) }));
    await client.initialize();
    await expect(client.save('x')).rejects.toThrow(/pair/i);
    expect(storage.remove).toHaveBeenCalledWith('captureToken');
  });

  it('captures only visible non-form text and bounds extraction before returning', () => {
    const ordinary = { closest: () => null, isContentEditable: false, parentElement: null, getClientRects: () => [{}] };
    const nodes = [
      { parentElement: { ...ordinary, closest: () => ({}) }, textContent: 'password or iframe' },
      { parentElement: { ...ordinary, hiddenForTest: true }, textContent: 'hidden' },
      { parentElement: ordinary, textContent: 'visible'.repeat(10000) },
      { parentElement: ordinary, textContent: 'not reached' },
    ];
    vi.stubGlobal('location', { protocol: 'https:', href: 'https://example.test' });
    vi.stubGlobal('NodeFilter', { SHOW_TEXT: 4 });
    vi.stubGlobal('getComputedStyle', (element) => ({ display: element.hiddenForTest ? 'none' : 'block' }));
    vi.stubGlobal('document', { contentType: 'text/html', title: 'Title', body: {}, createTreeWalker: () => { let n = 0; return { nextNode: () => nodes[n++] }; } });
    try {
      const result = extractPageText('page');
      expect(result.text).toHaveLength(50001);
      expect(result.text).not.toMatch(/password|iframe|hidden|not reached/);
    } finally { vi.unstubAllGlobals(); }
  });

  it('popup opening does not inject; edits invalidate a frozen preview and save sends only its ID', async () => {
    const elements: Record<string, any> = {};
    const ids = ['extension-id', 'pair-code', 'pair', 'forget', 'pair-status', 'selection', 'page', 'title', 'url', 'text', 'editor', 'preview', 'save', 'frozen', 'frozen-title', 'frozen-url', 'frozen-text', 'destination', 'warning', 'status', 'clipping'];
    for (const id of ids) elements[id] = { value: '', textContent: '', disabled: false, hidden: false, addEventListener(event, handler) { this[event] = handler; } };
    const doc = { getElementById: (id) => elements[id] };
    const client = { initialize: vi.fn(async () => true), pair: vi.fn(), forget: vi.fn(), preview: vi.fn(async () => ({ previewId: 'immutable', title: 'Normalized', url: 'https://example.test/', text: 'literal', mode: 'selection', destination: 'Bej Captures/Web', duplicate: true, existingPath: 'Bej Captures/Web/existing.md' })), save: vi.fn(async () => ({ path: 'Bej Captures/Web/existing.md', duplicate: true })) };
    const chrome = { runtime: { id: 'extension-id' }, tabs: { query: vi.fn(async () => [{ id: 1, url: 'https://example.test' }]) }, scripting: { executeScript: vi.fn(async () => [{ result: { title: 'Title', url: 'https://example.test', text: 'literal' } }]) } };
    await initializePopup(doc, chrome, client);
    expect(chrome.scripting.executeScript).not.toHaveBeenCalled();
    expect(elements['extension-id'].textContent).toBe('extension-id');
    await elements.selection.click();
    await elements.preview.click();
    expect(elements['frozen-title'].textContent).toBe('Normalized');
    expect(elements.warning.textContent).toMatch(/already|duplicate/i);
    elements.text.value = 'edited';
    elements.text.input();
    expect(elements.save.disabled).toBe(true);
    await elements.save.click();
    expect(client.save).not.toHaveBeenCalled();
    await elements.preview.click();
    await elements.save.click();
    expect(client.save).toHaveBeenCalledWith('immutable');
    expect(elements.status.textContent).toContain('Bej Captures/Web/existing.md');
    await elements.save.click();
    expect(client.save).toHaveBeenCalledTimes(1);
  });
});
