import React, { useEffect, useState } from 'react';
import { api, BejStatus, RunAction } from './api';

type Preview = { previewId: string; expiresAt: number; date: string; operations: { kind: string; title: string; titleShortened?: boolean; start: string; end: string }[] };
type ReminderState = Record<'discord' | 'desktop', { pending: number; paused: boolean }>;
export function Publishing({ planId, hasBlocks, status, busy, run, notify }: { planId: string; hasBlocks: boolean; status: BejStatus | null; busy: string; run: RunAction; notify: (message: string) => void }) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [reminders, setReminders] = useState<ReminderState | null>(null);
  const [loadError, setLoadError] = useState(false);
  useEffect(() => {
    let active = true;
    setPreview(null); setReminders(null);
    const load = () => api<ReminderState>(`plans/${planId}/reminders`).then(value => { if (active) { setReminders(value); setLoadError(false); } }).catch(() => { if (active) setLoadError(true); });
    load(); const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [planId]);
  const toggle = (channel: 'discord' | 'desktop') => run(`toggle-${channel}`, async () => {
    const enabled = !!reminders?.[channel].pending;
    const result = await api<{ armed?: number }>(`reminders/${enabled ? 'disarm' : 'arm'}`, { planId, channel });
    setReminders(await api<ReminderState>(`plans/${planId}/reminders`));
    notify(enabled ? `${channel === 'discord' ? 'Discord' : 'Desktop'} reminders turned off for this plan. A delivery already in progress may still arrive.` : `${result.armed || 0} reminders queued. Keep Bej running; quiet hours are 10 PM–6 AM. Previously sent or uncertain reminders are not sent again.`);
  });
  return <div className="publishing">
    <h3>Connect this plan</h3><p>Review calendar changes before publishing. Reminder switches control only this plan’s pending alerts.</p>
    <div className="plan-actions"><button className="button secondary" disabled={!!busy || !hasBlocks || !status?.outlook.configured} onClick={() => run('outlook-preview', async () => { setPreview(await api<Preview>('outlook/preview', { planId })); })}>Review Outlook calendar changes</button></div>
    <p>See the task titles and time blocks Bej would create or update in your Bej calendar. Nothing is published until you approve.</p>
    <div className="reminder-switches">{(['discord', 'desktop'] as const).map(channel => {
      const current = reminders?.[channel];
      const on = !!current?.pending;
      return <div className="reminder-switch-row" key={channel}><div><span id={`${channel}-reminder-label`}>{channel === 'discord' ? 'Discord' : 'Desktop'} reminders</span><small>{on ? `${current.pending} pending${current.paused ? ' · delivery paused in Reminders' : ''}` : 'Off'} · this plan</small></div><button type="button" role="switch" aria-checked={on} aria-labelledby={`${channel}-reminder-label`} className="reminder-switch" disabled={!!busy || !reminders || loadError || (!on && (!hasBlocks || (channel === 'discord' && !status?.discord.tokenStored)))} onClick={() => toggle(channel)}><span className="switch-track" aria-hidden="true"><span /></span><span>{on ? 'On' : 'Off'}</span></button></div>;
    })}</div>
    {loadError && <p className="connection-error" role="status">Could not refresh reminder status. Reconnecting…</p>}
    {preview && <section className="approval-box" aria-label="Outlook publication approval"><h3>Review exactly what goes to Outlook</h3><p>Destination: your separate Bej calendar. Titles and times only; no source notes or attendees. Approval expires at {new Date(preview.expiresAt * 1000).toLocaleTimeString('en', { timeZone: 'Asia/Manila' })} Manila time.</p><ul>{preview.operations.map((operation, index) => <li key={index}><strong>{operation.kind}: {operation.title}</strong><span>{operation.start} → {operation.end}</span>{operation.titleShortened && <span className="calendar-title-notice">Calendar title shortened to 255 characters or fewer. Your full task and source note stay unchanged.</span>}</li>)}</ul><div className="plan-actions"><button className="button primary" disabled={!!busy} onClick={() => run('outlook-publish', async () => { const result = await api<{ success: boolean; completed: string[]; failed: { error: string }[] }>('outlook/publish', { previewId: preview.previewId }); notify(result.success ? `Confirmed ${result.completed.length} Outlook task blocks.` : `Some calendar changes were not confirmed: ${result.failed.map(f => f.error).join(' ')}`); if (result.success) setPreview(null); })}>Approve and publish these blocks</button><button className="button secondary" disabled={!!busy} onClick={() => setPreview(null)}>Cancel publication</button></div></section>}
  </div>;
}
