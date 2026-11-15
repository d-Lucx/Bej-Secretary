import React, { useEffect, useState } from 'react';
import { api, RunAction } from './api';

type Item = { id: string; channel: string; due: number; state: string; last_error?: string; data: { title: string; date: string; start: string } };
export function Reminders({ busy, run, notify }: { busy: string; run: RunAction; notify: (message: string) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [enabled, setEnabled] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const load = async () => { const result = await api<{ reminders: Item[]; discordEnabled: boolean }>('reminders'); setItems(result.reminders); setEnabled(result.discordEnabled); };
  useEffect(() => { load().catch(() => {}); const timer = setInterval(() => { load().catch(() => {}); }, 10000); return () => clearInterval(timer); }, []);
  const active = items.filter(item => ['pending', 'sending'].includes(item.state));
  const history = items.filter(item => !['pending', 'sending'].includes(item.state));
  const visible = showHistory ? history : active;
  return <section className="panel"><div className="panel-heading"><div><h2>Reminder queue</h2><p>Active alerts are separate from delivery history. Canceled or sent records are not queued again.</p></div><button className="button secondary" role="switch" aria-checked={enabled} disabled={!!busy} onClick={() => run('pause-reminders', async () => { await api('reminders/settings', { channel: 'discord', enabled: !enabled }); await load(); notify(enabled ? 'Discord reminders paused.' : 'Discord reminders resumed.'); })}>Discord delivery: {enabled ? 'On' : 'Off'}</button></div>
    <p className="completion-help">A reminder is an alert, not proof of completion. Check the task in Obsidian, or use Source inbox → Propose task edit → Mark this task complete, then approve the preview. Bej checks the source before delivery.</p>
    <div className="plan-actions" aria-label="Reminder view"><button className="button secondary" aria-pressed={!showHistory} onClick={() => setShowHistory(false)}>Active ({active.length})</button><button className="button secondary" aria-pressed={showHistory} onClick={() => setShowHistory(true)}>History ({history.length})</button></div>
    {!visible.length ? <p className="inline-empty">{showHistory ? 'No delivery history yet.' : 'No active reminders. Turn them on for a draft in Today.'}</p> : <div className="task-list">{visible.map(item => <article className="task-row" key={item.id}><span className="tag">{item.state} · {item.channel}</span><h3>{item.data.title}</h3><p>{item.data.date} · {item.data.start} Manila time</p>{item.last_error && <p className="connection-error">{item.last_error}</p>}{item.state === 'pending' && <button className="text-button" disabled={!!busy} onClick={() => run('cancel-reminder', async () => { await api(`reminders/${item.id}/cancel`, {}); await load(); })}>Cancel this reminder</button>}</article>)}</div>}
  </section>;
}
