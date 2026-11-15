import React, { useEffect, useState } from 'react';
import { api, RunAction } from './api';

type Item = { id: string; channel: string; due: number; state: string; last_error?: string; data: { title: string; date: string; start: string } };
export function Reminders({ busy, run, notify }: { busy: string; run: RunAction; notify: (message: string) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [enabled, setEnabled] = useState(false);
  const load = async () => { const result = await api<{ reminders: Item[]; discordEnabled: boolean }>('reminders'); setItems(result.reminders); setEnabled(result.discordEnabled); };
  useEffect(() => { load().catch(() => {}); const timer = setInterval(() => { load().catch(() => {}); }, 10000); return () => clearInterval(timer); }, []);
  return <section className="panel"><div className="panel-heading"><div><h2>Reminder queue</h2><p>Persistent delivery status. Missed reminders expire after 30 minutes; uncertain sends are not retried blindly.</p></div><button className="button secondary" disabled={!!busy} onClick={() => run('pause-reminders', async () => { await api('reminders/settings', { channel: 'discord', enabled: !enabled }); await load(); notify(enabled ? 'Discord reminders paused.' : 'Discord reminders resumed.'); })}>{enabled ? 'Pause Discord reminders' : 'Resume Discord reminders'}</button></div>
    {!items.length ? <p className="inline-empty">No reminders armed yet. Choose a draft in Today and enable its reminders.</p> : <div className="task-list">{items.map(item => <article className="task-row" key={item.id}><span className="tag">{item.state} · {item.channel}</span><h3>{item.data.title}</h3><p>{item.data.date} · {item.data.start} Manila time</p>{item.last_error && <p className="connection-error">{item.last_error}</p>}{item.state === 'pending' && <button className="text-button" disabled={!!busy} onClick={() => run('cancel-reminder', async () => { await api(`reminders/${item.id}/cancel`, {}); await load(); })}>Cancel this reminder</button>}</article>)}</div>}
  </section>;
}
