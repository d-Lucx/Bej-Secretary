import React, { useEffect, useRef, useState } from 'react';
import { FileText, Globe, ShieldCheck } from 'lucide-react';
import { api, RunAction } from './api';
import './web-notes.css';

type WebStatus = { extensionId: string | null; paired: boolean; pairingExpiresAt?: string; destination: string };
type Preview = { previewId: string; expiresAt: string; title: string; url: string; text: string; mode: string; destination: string; duplicate: boolean; existingPath?: string; warning?: string };
type Capture = { id: string; title: string; url: string; mode: string; path: string; createdAt: string; missing: boolean; modified: boolean };
type DeletePreview = { previewId: string; title: string; path: string; missing?: boolean };
const DESTINATION = 'Bej Captures/Web';
const formatTime = (value: string) => new Date(value).toLocaleString('en', { timeZone: 'Asia/Manila' });

export function WebNotes({ active, busy, run, notify, vaultName }: { active: boolean; busy: string; run: RunAction; notify: (message: string) => void; vaultName?: string }) {
  const [status, setStatus] = useState<WebStatus | null>(null);
  const [extensionId, setExtensionId] = useState('');
  const [pairing, setPairing] = useState<{ pairingCode: string; expiresAt: string } | null>(null);
  const [draft, setDraft] = useState({ title: '', url: '', text: '' });
  const [preview, setPreview] = useState<Preview | null>(null);
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [deletion, setDeletion] = useState<DeletePreview | null>(null);
  const [now, setNow] = useState(Date.now());
  const previewHeading = useRef<HTMLHeadingElement>(null);
  const deleteHeading = useRef<HTMLHeadingElement>(null);
  const loadLibrary = async () => setCaptures((await api<{ captures: Capture[] }>('web/captures')).captures);
  const refresh = async () => {
    const result = await api<WebStatus>('web/status');
    setStatus(result); setExtensionId(result.extensionId || '');
    await loadLibrary(); setLoaded(true); setLoadError('');
  };
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    Promise.all([api<WebStatus>('web/status'), api<{ captures: Capture[] }>('web/captures')]).then(([connection, library]) => {
      if (cancelled) return;
      setStatus(connection); setExtensionId(connection.extensionId || ''); setCaptures(library.captures); setLoaded(true); setLoadError('');
    }).catch(error => { if (!cancelled) setLoadError(error instanceof Error ? error.message : 'Web notes could not be loaded.'); });
    return () => { cancelled = true; };
  }, [active]);
  useEffect(() => {
    if (!active || (!pairing && !preview)) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active, pairing, preview]);
  useEffect(() => { if (preview) previewHeading.current?.focus(); }, [preview]);
  useEffect(() => { if (deletion) deleteHeading.current?.focus(); }, [deletion]);
  const change = (field: keyof typeof draft, value: string) => { setDraft(current => ({ ...current, [field]: value })); setPreview(null); };
  const previewExpired = !!preview && new Date(preview.expiresAt).getTime() <= now;
  const pairingExpired = !!pairing && new Date(pairing.expiresAt).getTime() <= now;
  const obsidianLink = (path: string) => `obsidian://open?vault=${encodeURIComponent(vaultName || '')}&file=${encodeURIComponent(path)}`;

  return <div className="web-notes" hidden={!active}>
    <div className="web-privacy"><ShieldCheck size={19} aria-hidden="true" /><p>Capture only what you choose. Text stays local, with no cloud AI, screenshots or browser history. Saved web notes do not become tasks.</p></div>
    {loadError && <p className="message error" role="alert">{loadError}</p>}
    <div className="web-layout">
      <section className="panel web-paste" aria-labelledby="web-paste-heading">
        <div className="web-section-heading"><FileText size={20} aria-hidden="true" /><div><h2 id="web-paste-heading">Paste a webpage</h2><p>Review the text, then approve a new note.</p></div></div>
        <form onSubmit={event => { event.preventDefault(); run('web-preview', async () => { setPreview(null); const result = await api<Preview>('web/preview', { ...draft, mode: 'paste' }); setNow(Date.now()); setPreview(result); }); }}>
          <fieldset disabled={!!busy} className="web-fields">
            <label htmlFor="web-title">Note title</label><input id="web-title" required maxLength={500} value={draft.title} onChange={e => change('title', e.target.value)} />
            <label htmlFor="web-url">Source URL <span>HTTP or HTTPS</span></label><input id="web-url" type="url" required maxLength={4000} pattern="https?://.+" value={draft.url} onChange={e => change('url', e.target.value)} aria-describedby="web-url-help" /><p id="web-url-help" className="web-help">Bej records this address without opening or downloading it.</p>
            <div className="web-field-heading"><label htmlFor="web-text">Page text</label><span>{draft.text.length.toLocaleString()} / 50,000</span></div><textarea id="web-text" required maxLength={50000} rows={10} value={draft.text} onChange={e => change('text', e.target.value)} aria-describedby="web-text-help" /><p id="web-text-help" className="web-help">Paste only what you want to keep. Formatting and task-like text are saved as literal text.</p>
            <button className="button secondary" type="submit" disabled={!!busy || !draft.title.trim() || !draft.url.trim() || !draft.text.trim()}>{busy === 'web-preview' ? 'Preparing preview…' : 'Preview new note'}</button><button className="text-button" type="button" disabled={!!busy} onClick={() => { setDraft({ title: '', url: '', text: '' }); setPreview(null); }}>Clear pasted draft</button>
          </fieldset>
        </form>
        {preview && <section className="web-review" aria-labelledby="web-review-heading">
          <h3 id="web-review-heading" tabIndex={-1} ref={previewHeading}>Review this new note</h3><p>Saving approves exactly this preview. Editing the fields above requires a new preview.</p>
          <dl className="web-metadata"><div><dt>Destination</dt><dd>{preview.destination}{vaultName && ` · ${vaultName}`}</dd></div><div><dt>Title</dt><dd>{preview.title}</dd></div><div><dt>Source URL</dt><dd>{preview.url}</dd></div><div><dt>Capture method</dt><dd>{preview.mode}</dd></div><div><dt>Preview expires</dt><dd>{formatTime(preview.expiresAt)} Manila</dd></div></dl>
          <div className="web-preview-text" aria-label="Exact captured text">{preview.text}</div>
          {preview.warning && <p className="web-warning">{preview.warning}</p>}
          {preview.duplicate && <p className="web-warning">Already saved{preview.existingPath ? ` at ${preview.existingPath}` : ''}. Saving reuses the existing note.</p>}
          {previewExpired && <p className="web-warning" role="status">This preview expired. Prepare a new preview before saving.</p>}
          <div className="web-actions"><button className="button primary" disabled={!!busy || previewExpired} onClick={() => run('web-save', async () => {
            const result = await api<{ path: string; duplicate: boolean }>('web/save', { previewId: preview.previewId });
            setPreview(null); notify(`${result.duplicate ? 'Reused the existing note' : 'Saved a new web note'}: ${result.path}. No tasks were created.`); await loadLibrary();
          })}>{busy === 'web-save' ? 'Saving note…' : `Save new note to ${DESTINATION}`}</button><button className="button secondary" disabled={!!busy} onClick={() => setPreview(null)}>Discard preview</button></div>
        </section>}
      </section>
      <aside className="panel web-connection" aria-labelledby="web-connection-heading">
        <div className="web-section-heading"><Globe size={20} aria-hidden="true" /><div><h2 id="web-connection-heading">Browser connection</h2><p>{!status ? 'Connection status unavailable' : status.paired ? 'Extension paired' : 'No extension paired'}</p></div></div>
        <p>Use the extension to capture selected text, or deliberately choose the loaded page’s visible text. Nothing runs until you choose it.</p>
        <details><summary>Set up Chrome or Edge</summary><ol><li>Open <code>chrome://extensions</code> or <code>edge://extensions</code> and enable Developer mode.</li><li>Choose <strong>Load unpacked</strong> and select <code>C:\Yan2_Projects\Bej-Secretary\bej-browser-extension</code>.</li><li>Copy the extension ID into the field below. Generate a code here, then paste it into the extension popup.</li></ol><p>Install manually. Browser-internal pages and PDFs are unsupported. Selected text never silently falls back to a full page.</p></details>
        <form onSubmit={event => { event.preventDefault(); run('web-pair', async () => { setPairing(null); const result = await api<{ pairingCode: string; expiresAt: string }>('web/pairing', { extensionId: extensionId.trim() }); setNow(Date.now()); setPairing(result); setStatus(await api<WebStatus>('web/status')); }); }}>
          <label className="web-extension-label" htmlFor="web-extension-id">Extension ID</label><input id="web-extension-id" required pattern="[a-p]{32}" minLength={32} maxLength={32} spellCheck={false} autoComplete="off" value={extensionId} disabled={!!busy} onChange={e => { setExtensionId(e.target.value); setPairing(null); }} aria-describedby="web-extension-help" /><p id="web-extension-help" className="web-help">32 lowercase letters, a–p. A new code replaces any pending code. Generating a new code immediately revokes the previous browser connection.</p>
          <button className="button secondary" type="submit" disabled={!!busy || !/^[a-p]{32}$/.test(extensionId)}>{busy === 'web-pair' ? 'Generating code…' : 'Generate pairing code'}</button>
        </form>
        {pairing && <div className="web-pairing" role="status"><strong>{pairingExpired ? 'Pairing code expired' : 'One-use pairing code'}</strong>{!pairingExpired && <code className="web-pairing-code">{pairing.pairingCode}</code>}<p>Expires {formatTime(pairing.expiresAt)} Manila. Paste into the extension only; keep it out of chat and notes.</p><button className="text-button" onClick={() => setPairing(null)}>Hide pairing code</button></div>}
        <div className="web-actions"><button className="button secondary" disabled={!!busy} onClick={() => run('web-refresh', refresh)}>Refresh connection and library</button><button className="text-button web-danger" disabled={!!busy || (!status?.paired && !status?.pairingExpiresAt && !pairing)} onClick={() => run('web-revoke', async () => { await api('web/revoke', {}); setPairing(null); setStatus(await api<WebStatus>('web/status')); notify('Browser access revoked. Pair again to reconnect. Saved notes remain in your vault.'); })}>Revoke browser access</button></div>
      </aside>
    </div>
    <section className="panel web-library" aria-labelledby="web-library-heading"><div className="panel-heading"><div><h2 id="web-library-heading">Saved web notes <span className="subcount">{captures.length}</span></h2><p>Stored in {DESTINATION}. Kept until you explicitly delete them.</p></div></div>
      {!captures.length && <p className="inline-empty">{loaded ? 'No web notes saved yet. Preview pasted text above, or use your paired extension.' : 'The saved library has not loaded yet.'}</p>}
      {captures.map(capture => <article className="web-library-row" key={capture.id}><div><h3>{capture.title}</h3><p className="web-source-url">{capture.url}</p><p className="web-help">{formatTime(capture.createdAt)} Manila · {capture.mode === 'page' ? 'Visible page text' : capture.mode === 'selection' ? 'Selected text' : 'Pasted text'}</p><p className="path">{capture.path}</p><div className="web-labels">{capture.missing ? <span className="web-warning">Note missing</span> : capture.modified ? <span className="web-warning">Modified in vault · delete manually in Obsidian</span> : <span className="tag">Saved capture</span>}</div></div><div className="web-library-actions">{vaultName && !capture.missing && <a className="button secondary" href={obsidianLink(capture.path)}>Open in Obsidian</a>}<button className="text-button web-danger" disabled={!!busy || capture.modified} onClick={() => run('web-delete-preview', async () => { setDeletion(null); setDeletion(await api<DeletePreview>('web/delete-preview', { captureId: capture.id })); })}>Review deletion</button></div></article>)}
      {deletion && <section className="web-delete-review" aria-labelledby="web-delete-heading"><h3 id="web-delete-heading" tabIndex={-1} ref={deleteHeading}>Approve deletion of this capture</h3><dl className="web-metadata"><div><dt>Title</dt><dd>{deletion.title}</dd></div><div><dt>Exact note</dt><dd>{deletion.path}</dd></div></dl><p>{deletion.missing ? 'The note is already missing. This removes only its local library record.' : 'This deletes the unchanged generated note and its local library record. If the note has changed, deletion will be refused.'} Existing backups may retain copies.</p><div className="web-actions"><button className="button secondary web-danger" disabled={!!busy} onClick={() => run('web-delete', async () => { await api('web/delete', { previewId: deletion.previewId }); setDeletion(null); notify(deletion.missing ? 'Removed the approved library record. Its note was already missing.' : 'Deleted the approved web note and its local record.'); await loadLibrary(); })}>{deletion.missing ? 'Approve removal of this record' : 'Approve deletion of this note'}</button><button className="button secondary" disabled={!!busy} onClick={() => setDeletion(null)}>Cancel deletion</button></div></section>}
    </section>
  </div>;
}
