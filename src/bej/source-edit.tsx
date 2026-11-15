import React, { useState } from 'react';
import { api, RunAction } from './api';

export function SourceEdit({ task, busy, run, close, applied }: { task: { id: string; title: string; source: string; line: number }; busy: string; run: RunAction; close: () => void; applied: () => void }) {
  const [text, setText] = useState(task.title);
  const [completed, setCompleted] = useState(false);
  const [preview, setPreview] = useState<{ previewId: string; before: string; after: string } | null>(null);
  return <section className="approval-box" aria-label="Source task edit"><h3>Edit an existing task</h3><p>{task.source} · line {task.line}. Nothing changes until you approve the exact preview.</p><label className="secret-label">Task text<input value={text} maxLength={1000} onChange={e => { setText(e.target.value); setPreview(null); }} /></label><label className="check-label"><input type="checkbox" checked={completed} onChange={e => { setCompleted(e.target.checked); setPreview(null); }} />Mark this task complete</label><div className="plan-actions"><button className="button secondary" disabled={!!busy || !text.trim()} onClick={() => run('source-preview', async () => { setPreview(await api('source-edits/preview', { taskId: task.id, text, completed })); })}>Preview exact source edit</button><button className="button secondary" disabled={!!busy} onClick={close}>Cancel edit</button></div>
    {preview && <div className="source-diff"><span>Before</span><pre>{preview.before}</pre><span>After</span><pre>{preview.after}</pre><p>A private backup is kept. If the source changed since this preview, Bej will refuse the write.</p><button className="button primary" disabled={!!busy} onClick={() => run('source-apply', async () => { await api('source-edits/apply', { previewId: preview.previewId }); applied(); })}>Approve this source edit</button></div>}
  </section>;
}
