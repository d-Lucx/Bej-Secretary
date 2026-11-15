import { captureActiveTab, createCaptureClient } from './capture.js';

export async function initializePopup(doc, chromeApi, client = createCaptureClient(chromeApi)) {
  const el = id => doc.getElementById(id);
  let mode = 'selection';
  let preview = null;
  let revision = 0;
  let busy = false;
  let paired = false;
  let storageReady = false;
  const controls = ['pair', 'forget', 'selection', 'page', 'preview', 'title', 'url', 'text', 'pair-code'];
  function refresh() {
    for (const id of controls) el(id).disabled = busy;
    el('pair').disabled = busy || !storageReady;
    for (const id of ['selection', 'page', 'preview']) el(id).disabled = busy || !paired;
    el('save').disabled = busy || !paired || !preview;
  }
  function invalidate() { revision++; preview = null; el('frozen').hidden = true; el('save').disabled = true; }
  async function run(work) {
    if (busy) return;
    busy = true; refresh(); el('status').textContent = 'Working locally…';
    try { await work(); } catch (error) {
      el('status').textContent = error.message;
      if (storageReady) {
        try { paired = await client.initialize(); }
        catch { paired = false; storageReady = false; }
        if (!paired) el('pair-status').textContent = 'Not paired. Connect again in Bej.';
      }
    }
    finally { busy = false; refresh(); }
  }
  el('extension-id').textContent = chromeApi.runtime.id;
  for (const id of ['title', 'url', 'text']) el(id).addEventListener('input', invalidate);
  el('pair').addEventListener('click', () => run(async () => {
    invalidate();
    const code = el('pair-code').value;
    el('pair-code').value = '';
    await client.pair(code);
    paired = true; el('pair-status').textContent = 'Paired with local Bej.'; el('status').textContent = 'Ready for a manual capture.';
  }));
  el('forget').addEventListener('click', () => run(async () => {
    invalidate(); await client.forget(); paired = false;
    el('pair-status').textContent = 'Not paired.'; el('status').textContent = 'Local credential removed. Revoke in Bej to invalidate all copies.';
  }));
  for (const captureMode of ['selection', 'page']) el(captureMode).addEventListener('click', () => run(async () => {
    invalidate();
    let captured;
    try { captured = await captureActiveTab(chromeApi, captureMode); }
    catch (error) {
      // Chrome injection errors can include source details. Only show known local validation errors.
      if (/empty|HTTP\(S\)|Title must|URL must|No supported/.test(error.message)) throw error;
      throw new Error('Cannot read this page. Select ordinary page text or paste it in desktop Bej. Browser pages and PDFs are unsupported.');
    }
    mode = captureMode;
    el('title').value = captured.title; el('url').value = captured.url; el('text').value = captured.text;
    el('clipping').textContent = captured.truncated ? 'Capture was clipped for size or page-complexity limits. Review the excerpt before saving.' : '';
    el('editor').hidden = false; el('status').textContent = 'Review the captured fields, then create a save preview.';
  }));
  el('preview').addEventListener('click', () => run(async () => {
    invalidate();
    const currentRevision = revision;
    const result = await client.preview({ title: el('title').value, url: el('url').value, text: el('text').value, mode });
    if (revision !== currentRevision) { el('status').textContent = 'Fields changed. Create a fresh preview.'; return; }
    preview = result;
    for (const field of ['title', 'url', 'text']) el(`frozen-${field}`).textContent = result[field];
    el('destination').textContent = result.destination;
    el('warning').textContent = [result.duplicate ? `Already saved: ${result.existingPath || 'an existing capture'}. Saving reuses the existing note.` : '', result.warning || ''].filter(Boolean).join(' ');
    el('frozen').hidden = false;
    el('status').textContent = 'Review the frozen note below. Any field edit cancels approval.';
  }));
  el('save').addEventListener('click', () => {
    if (!preview || busy || !paired) return;
    return run(async () => {
      const approved = preview;
      preview = null;
      if (approved.expiresAt && Date.parse(approved.expiresAt) <= Date.now()) { invalidate(); throw new Error('Preview expired. Create a fresh preview.'); }
      const result = await client.save(approved.previewId);
      el('status').textContent = `${result.duplicate ? 'Existing note reused' : 'Saved'}: ${result.path}`;
    });
  });
  busy = true; refresh();
  try {
    paired = await client.initialize();
    storageReady = true;
    el('pair-status').textContent = paired ? 'Paired with local Bej.' : 'Connect to desktop Bej to begin.';
  } catch { el('status').textContent = 'Trusted local storage is unavailable. Update Chrome or Edge before pairing.'; }
  finally { busy = false; refresh(); }
}

if (typeof document !== 'undefined' && typeof chrome !== 'undefined' && chrome.runtime?.id && chrome.storage?.local) initializePopup(document, chrome);
