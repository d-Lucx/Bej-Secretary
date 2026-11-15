import React, { useState } from 'react';
import { api, RunAction } from './api';

export function PlanChange({ planId, busy, run, changed }: { planId: string; busy: string; run: RunAction; changed: (plan: any) => void }) {
  const [start, setStart] = useState('08:00');
  const [end, setEnd] = useState('10:00');
  const [reason, setReason] = useState('Unexpected change');
  return <details className="plan-change"><summary>Plans changed? Protect some time.</summary><p>Add an unavailable window for this date. Bej will rearrange flexible local tasks, update already-armed reminders, and leave fixed Outlook commitments and source notes unchanged. Review Outlook changes separately.</p><div className="change-fields"><label>Unavailable from<input type="time" value={start} onChange={e => setStart(e.target.value)} /></label><label>Until<input type="time" value={end} onChange={e => setEnd(e.target.value)} /></label><label>Reason<input value={reason} maxLength={160} onChange={e => setReason(e.target.value)} /></label></div><button className="button secondary" disabled={!!busy || !reason.trim()} onClick={() => run('reflow', async () => { changed(await api('plan/reflow', { planId, start, end, reason })); })}>Rearrange flexible tasks</button></details>;
}
