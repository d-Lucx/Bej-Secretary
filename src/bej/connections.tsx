import React, { useEffect, useState } from 'react';
import { CalendarDays, FolderOpen, Link2, LockKeyhole, RefreshCw, Sparkles, Monitor } from 'lucide-react';
import { api, BejStatus, RunAction } from './api';

type Props = { status: BejStatus | null; busy: string; day: string; run: RunAction; onStatus: (status: BejStatus) => void; notify: (message: string) => void };

export function Connections({ status, busy, day, run, onStatus, notify }: Props) {
  const [clientId, setClientId] = useState(status?.outlook.clientId || '');
  const [botToken, setBotToken] = useState('');
  const [signIn, setSignIn] = useState<{ user_code: string; verification_uri: string } | null>(null);
  const refresh = async () => onStatus(await api<BejStatus>('status'));
  useEffect(() => { if (status?.outlook.clientId) setClientId(status.outlook.clientId); }, [status?.outlook.clientId]);
  useEffect(() => {
    if (!status?.outlook.authPending) return;
    const timer = window.setInterval(() => { refresh().catch(() => {}); }, 3000);
    return () => window.clearInterval(timer);
  }, [status?.outlook.authPending]);

  return <div className="connections-grid">
    <section className="panel"><div className="connection-head"><FolderOpen size={22} aria-hidden="true" /><span className="tag">{status?.vaultExists ? 'Folder available' : 'Check access'}</span></div><h2>Obsidian vault</h2><p className="path">{status?.vaultPath || 'Waiting for local service…'}</p><p>All content folders are readable. Generated plans stay in <strong>Bej Plans</strong>. Existing task edits require an exact preview and your approval.</p></section>
    <section className="panel"><div className="connection-head"><Sparkles size={22} aria-hidden="true" /><span className="tag">{status?.ollama.modelReady ? 'Model ready' : status?.ollama.available ? 'Model needed' : 'Not reachable'}</span></div><h2>Local AI · Ollama</h2><p>Planning works without AI. Explanations use a small local model and unload it afterward.</p><code>ollama pull qwen2.5:0.5b</code><button className="text-button" disabled={!!busy} onClick={() => run('status', refresh)}>Refresh connection status <RefreshCw size={14} aria-hidden="true" /></button></section>
    <section className="panel"><div className="connection-head"><CalendarDays size={22} aria-hidden="true" /><span className="tag">{status?.outlook.connected ? 'Signed in' : status?.outlook.authPending ? 'Waiting for sign-in' : status?.outlook.calendarId ? 'Account saved' : 'Sign-in needed'}</span></div><h2>Outlook · Bej calendar</h2><p>Use your personal Microsoft account. Only approved task titles and times are published to your separate Bej calendar.</p>
      <label className="secret-label">Microsoft application (client) ID<input value={clientId} onChange={e => setClientId(e.target.value)} autoComplete="off" placeholder="Enter the nonsecret client ID" /></label>
      <button className="button secondary" disabled={!!busy || clientId.trim().length !== 36 || !!status?.outlook.authPending} onClick={() => run('login', async () => { await api('outlook/configure', { clientId: clientId.trim() }); setSignIn(await api('outlook/login', {})); await refresh(); })}>Connect personal Outlook</button>
      {signIn && !status?.outlook.connected && <div className="auth-code"><p>Open <a href={signIn.verification_uri} target="_blank" rel="noreferrer">Microsoft sign-in</a> and enter:</p><strong>{signIn.user_code}</strong><p>Review the Microsoft consent screen. Bej never receives your password.</p></div>}
      {status?.outlook.error && <p role="alert" className="connection-error">{status.outlook.error}</p>}
      <button className="text-button" disabled={!!busy || !status?.outlook.configured} onClick={() => run('sync', async () => { const result = await api<{ stale: boolean; busy: unknown[]; error?: string }>('outlook/sync', { date: day }); await refresh(); notify(result.stale ? result.error || 'Outlook is unavailable. Cached availability is marked stale.' : `Outlook refreshed for ${day}: ${result.busy.length} busy periods. Rebuild your draft to use them.`); })}>Refresh calendar for {day} <RefreshCw size={14} aria-hidden="true" /></button>
      <p className="muted-note">{status?.outlook.lastSyncedAt ? `Last sync: ${new Date(status.outlook.lastSyncedAt).toLocaleString('en', { timeZone: 'Asia/Manila' })} (Manila).` : 'No calendar data has been synchronized yet.'} Registration help is in OUTLOOK_SETUP.md. If Entra reports “Microsoft Services”, the registration account needs its own tenant.</p>
    </section>
    <section className="panel"><div className="connection-head"><Link2 size={22} aria-hidden="true" /><span className="tag">{status?.discord.deliveryVerified ? 'Delivery verified' : status?.discord.tokenStored ? 'Token saved' : 'Token needed'}</span></div><h2>Discord · private bot channel</h2><p>Your destination is configured. Only task names and reminder times are sent; mentions and link previews are suppressed.</p>
      <label className="secret-label">Bot token <span className="hint">Saved only in Windows Credential Manager</span><input type="password" autoComplete="off" value={botToken} onChange={e => setBotToken(e.target.value)} placeholder={status?.discord.tokenStored ? 'A token is already saved' : 'Enter locally, never in chat'} /></label>
      <div className="plan-actions"><button className="button secondary" disabled={!!busy || botToken.length < 20} onClick={() => run('credential', async () => { const result = await api<{ message: string }>('discord/credential', { token: botToken }); setBotToken(''); notify(result.message); await refresh(); })}><LockKeyhole size={15} aria-hidden="true" />Save token locally</button>
      <button className="button secondary" disabled={!!busy || !status?.discord.tokenStored} onClick={() => run('discord-validate', async () => { const result = await api<{ botName: string; channelName: string }>('discord/validate', {}); notify(`Verified ${result.botName} can access #${result.channelName}. No message sent.`); })}>Check channel access</button></div>
      <button className="text-button" disabled={!!busy || !status?.discord.tokenStored} onClick={() => run('discord-test', async () => { await api('discord/test', {}); notify('Sent “Bej Secretary: Discord connection test.” to your configured channel.'); await refresh(); })}>Send generic connection-test message <Link2 size={14} aria-hidden="true" /></button>
      <p className="muted-note">Enable reminders for a chosen draft from Today. Routine delivery pauses between 10 PM and 6 AM. The laptop must be awake, online, and running Bej.</p>
    </section>
    <section className="panel"><div className="connection-head"><Monitor size={22} aria-hidden="true" /><span className="tag">{status?.desktop?.startupEnabled ? 'Starts at sign-in' : 'Manual start'}</span></div><h2>Desktop and startup</h2><p>Desktop reminders work without Discord. Enable each draft explicitly. The tray icon can open Bej, pause reminders, or quit.</p><button className="button secondary" disabled={!!busy} onClick={() => run('startup', async () => { await api('desktop/startup', { enabled: !status?.desktop?.startupEnabled }); await refresh(); notify('Windows sign-in startup preference updated. Capture remains off.'); })}>{status?.desktop?.startupEnabled ? 'Disable sign-in startup' : 'Enable sign-in startup'}</button></section>
  </div>;
}
