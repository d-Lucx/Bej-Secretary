import React, { useEffect, useState } from 'react';
import { api, BejStatus, RunAction } from './api';

type Preview = { previewId: string; expiresAt: number; date: string; operations: { kind: string; title: string; start: string; end: string }[] };
export function Publishing({ planId, hasBlocks, status, busy, run, notify }: { planId: string; hasBlocks: boolean; status: BejStatus | null; busy: string; run: RunAction; notify: (message: string) => void }) {
  const [preview, setPreview] = useState<Preview | null>(null);
  useEffect(() => { setPreview(null); }, [planId]);
  return <div className="publishing">
    <h3>Connect this plan</h3><p>Saving a note does not publish events or enable reminders. Choose each action explicitly.</p>
    <div className="plan-actions"><button className="button secondary" disabled={!!busy || !hasBlocks || !status?.outlook.configured} onClick={() => run('outlook-preview', async () => { setPreview(await api<Preview>('outlook/preview', { planId })); })}>Preview Outlook task blocks</button>
      <button className="button secondary" disabled={!!busy || !hasBlocks || !status?.discord.tokenStored} onClick={() => run('arm-discord', async () => { const result = await api<{ armed: number }>('reminders/arm', { planId, channel: 'discord' }); notify(`Armed ${result.armed} Discord reminders for the displayed task names and start times. Quiet hours: 10 PM–6 AM.`); })}>Enable Discord reminders for this plan</button>
      <button className="button secondary" disabled={!!busy || !hasBlocks} onClick={() => run('arm-desktop', async () => { const result = await api<{ armed: number }>('reminders/arm', { planId, channel: 'desktop' }); notify(`Armed ${result.armed} desktop reminders. Keep Bej running; quiet hours are 10 PM–6 AM.`); })}>Enable desktop reminders</button>
    </div>
    {preview && <section className="approval-box" aria-label="Outlook publication approval"><h3>Review exactly what goes to Outlook</h3><p>Destination: your separate Bej calendar. Titles and times only; no source notes or attendees. Approval expires at {new Date(preview.expiresAt * 1000).toLocaleTimeString('en', { timeZone: 'Asia/Manila' })} Manila time.</p><ul>{preview.operations.map((operation, index) => <li key={index}><strong>{operation.kind}: {operation.title}</strong><span>{operation.start} → {operation.end}</span></li>)}</ul><div className="plan-actions"><button className="button primary" disabled={!!busy} onClick={() => run('outlook-publish', async () => { const result = await api<{ success: boolean; completed: string[]; failed: { error: string }[] }>('outlook/publish', { previewId: preview.previewId }); notify(result.success ? `Confirmed ${result.completed.length} Outlook task blocks.` : `Some calendar changes were not confirmed: ${result.failed.map(f => f.error).join(' ')}`); if (result.success) setPreview(null); })}>Approve and publish these blocks</button><button className="button secondary" disabled={!!busy} onClick={() => setPreview(null)}>Cancel publication</button></div></section>}
  </div>;
}
