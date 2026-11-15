import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowRight, CalendarDays, Check, ChevronRight, FileText, FolderOpen, LayoutDashboard, Link2, LockKeyhole, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';
import './style.css';
import { api, BejStatus } from './api';
import { Connections } from './connections';
import { Reminders } from './reminders';
import { Publishing } from './publishing';
import { SourceEdit } from './source-edit';
import { CapturePanel } from './capture';
import { PlanChange } from './plan-change';
import { Task, Choice, Plan } from './planning-types';
import { TaskOptions, PlanTask } from './task-planning';
import { usePlanProgress } from './use-plan-progress';

type Status = BejStatus;

function App() {
  const [tab, setTab] = useState<'today' | 'sources' | 'connections' | 'reminders' | 'capture'>(() => { const requested=new URLSearchParams(location.search).get('view'); return ['sources','connections','reminders','capture'].includes(requested || '') ? requested as 'sources'|'connections'|'reminders'|'capture' : 'today'; });
  const [status, setStatus] = useState<Status | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [day, setDay] = useState(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Manila' }).format(new Date()));
  const [capacity, setCapacity] = useState(240);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [saved, setSaved] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState('');
  const [filter, setFilter] = useState('');
  const [scanned, setScanned] = useState(false);
  const [scanWarnings, setScanWarnings] = useState<string[]>([]);
  const [explanation, setExplanation] = useState('');
  const [history, setHistory] = useState<{id:string;date:string;savedPath?:string}[]>([]);
  const [dayOff, setDayOff] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [recording, setRecording] = useState(false);
  const [completingTask, setCompletingTask] = useState(false);
  const { progress, progressError, refreshProgress } = usePlanProgress(plan?.id);
  useEffect(() => { if (editingTask) document.getElementById('source-edit-review')?.scrollIntoView({ block: 'start' }); }, [editingTask, completingTask]);
  const selected = Object.keys(choices).length;

  useEffect(() => { api<Status>('status').then(setStatus).catch(e => setError(e.message)); api<{plans:{id:string;date:string;savedPath?:string}[]}>('plans').then(r => setHistory(r.plans)).catch(() => {});const timer=setInterval(()=>{if(document.visibilityState==='visible')api<Status>('status').then(setStatus).catch(()=>{});},15000);return ()=>clearInterval(timer); }, []);
  useEffect(() => { let canceled=false; api<{workDayOff:boolean}>(`day-override/${day}`).then(r => {if(!canceled)setDayOff(r.workDayOff);}).catch(() => {}); return () => {canceled=true;}; }, [day]);
  const run = async (name: string, action: () => Promise<void>) => {
    setBusy(name); setError(''); setNotice('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : 'The local service did not respond. Your draft is unchanged.'); }
    finally { setBusy(''); }
  };
  const scan = () => run('scan', async () => {
    const result = await api<{ tasks: Task[]; noteCount: number; warnings: string[] }>('tasks');
    setTasks(result.tasks); setChoices({}); setScanned(true); setScanWarnings(result.warnings);
    setNotice(`Read ${result.noteCount} notes; found ${result.tasks.length} task candidates. Source notes unchanged.${result.warnings.length ? ` ${result.warnings.length} files need review.` : ''}`);
    setTab('sources');
  });
  const buildPlan = () => run('plan', async () => {
    const chosen = tasks.filter(t => choices[t.id]).map(t => ({ id: t.id, fingerprint: t.fingerprint, ...choices[t.id] }));
    const result = await api<Plan>('plan', { date: day, capacity, tasks: chosen });
    setPlan(result); setSaved(''); setExplanation(''); setTab('today'); setHistory((await api<{plans:{id:string;date:string;savedPath?:string}[]}>('plans')).plans);
    setNotice('Draft ready. Nothing has been written to Obsidian or Outlook.');
  });
  const toggle = (id: string) => setChoices(current => {
    const next = { ...current }; if (next[id]) delete next[id]; else { const task = tasks.find(item => item.id === id); next[id] = { category: task?.category || 'work', minutes: task?.minutes || 30, priority: task?.priority || 'normal', dueDate: task?.dueDate || null }; } return next;
  });
  const updateChoice = (id: string, change: Partial<Choice>) => setChoices(current => ({ ...current, [id]: { ...current[id], ...change } }));
  const friendlyDay = new Intl.DateTimeFormat('en', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' }).format(new Date(`${day}T12:00:00Z`));
  const deadlineWarnings = plan?.deadlineWarnings?.filter(warning => progress?.tasks[warning.taskId]?.status !== 'completed') || [];
  const filtered = tasks.filter(t => `${t.title} ${t.source}`.toLowerCase().includes(filter.toLowerCase()));

  return <div className="workspace">
    <a className="skip-link" href="#main">Skip to workspace</a>
    <aside className="sidebar">
      <a className="brand" href="#main" aria-label="Bej workspace"><span className="brand-mark">b.</span><span>bej<span className="brand-sub">Your local assistant</span></span></a>
      <div className="workspace-label">WORKSPACE</div>
      <nav aria-label="Workspace">{([
        ['today', LayoutDashboard, 'Today'], ['sources', FolderOpen, 'Source inbox'], ['connections', Link2, 'Connections'], ['reminders', CalendarDays, 'Reminders'], ['capture', FileText, 'Manual capture'],
      ] as const).map(([key, Icon, label]) => <button key={key} className={`nav-item ${tab === key ? 'active' : ''}`} aria-current={tab === key ? 'page' : undefined} onClick={() => setTab(key)}><Icon size={18} aria-hidden="true" />{label}{key === 'sources' && selected > 0 && <span className="count">{selected}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><ShieldCheck size={22} aria-hidden="true" /><strong>A little more private.</strong><p>Your notes and planning stay on this laptop. Connections are separate.</p><span className="local-indicator"><i /> Local workspace</span></div>
    </aside>
    <div className="content-shell">
      <header className="topbar"><span><LockKeyhole size={14} aria-hidden="true" /> Personal workspace</span><span>{recording && <button className="recording-indicator" onClick={()=>setTab('capture')}>Recording · open capture controls</button>}Manila <b>UTC+8</b></span></header>
      <main id="main" tabIndex={-1}>
        <div className="page-heading"><div><div className="eyebrow">{tab === 'today' ? 'MAKE ROOM FOR WHAT MATTERS' : tab === 'sources' ? 'FROM YOUR OBSIDIAN VAULT' : 'LOCAL FIRST. CONNECT BY CHOICE.'}</div><h1>{tab === 'today' ? 'Your day, with a plan.' : tab === 'sources' ? 'A place to begin.' : tab === 'reminders' ? 'Your reminders.' : tab === 'capture' ? 'Keep the useful moments.' : 'Your connections.'}</h1><p>{tab === 'today' ? 'Choose what matters today. Let Bej find room for it.' : tab === 'sources' ? 'Review candidates before they become commitments.' : 'See what is ready, what leaves your laptop, and what comes next.'}</p></div>{(tab === 'today' || tab === 'sources') && <button className="button secondary" onClick={scan} disabled={!!busy}><RefreshCw size={16} aria-hidden="true" />{busy === 'scan' ? 'Reading notes…' : scanned ? 'Rescan vault' : 'Read my vault'}</button>}</div>
        {error && <div className="message error" role="alert">{error}</div>}
        {notice && <div className="message" role="status">{notice}</div>}
        {editingTask && (tab === 'today' || tab === 'sources') && <div id="source-edit-review"><SourceEdit key={`${editingTask.id}-${completingTask}`} task={editingTask} initialCompleted={completingTask} busy={busy} run={run} close={() => setEditingTask(null)} applied={reviewNeeded => { setEditingTask(null); setTasks([]); setChoices({}); setScanned(false); refreshProgress(); setNotice(reviewNeeded ? 'Source edit applied with a private backup. Could not refresh reminders; review vault access and the queue.' : 'Source edit applied with a private backup. Pending reminders refreshed. Existing Outlook blocks remain unchanged. Rescan before building another draft.'); }} /></div>}
        {(tab === 'today' || tab === 'sources') && <section className="planner-controls" aria-label="Plan settings">
          <label>Plan date<input type="date" value={day} min={status?.today} onChange={e => { if (e.target.value) setDay(e.target.value); }} /></label>
          <label>Task capacity <span className="hint">Editable estimate, not your full workday</span><select value={capacity} onChange={e => setCapacity(Number(e.target.value))}>{[60, 120, 180, 240, 300, 360, 480].map(minutes => <option key={minutes} value={minutes}>{minutes / 60} hours</option>)}</select></label>
          <button className="button primary" disabled={!!busy || !selected} onClick={buildPlan}>Build daily draft <ArrowRight size={17} aria-hidden="true" /></button>
          <label className="check-label day-off"><input type="checkbox" checked={dayOff} disabled={!!busy} onChange={e => { const value=e.target.checked; run('day-off', async () => { await api('day-override', {date:day,workDayOff:value}); setDayOff(value); setNotice(`Availability exception saved for ${day}. Rebuild the draft to apply it.`); }); }} />Holiday / no work on this date</label>
        </section>}
        {tab === 'today' && <div className="today-grid"><section className="panel timeline"><div className="panel-heading"><div><div className="eyebrow">{plan ? 'DRAFT PLAN' : 'A FRESH START'}</div><h2>{plan ? plan.date : friendlyDay}</h2></div><span className="tag">{plan ? `${plan.scheduledMinutes} min planned` : 'No tasks chosen yet'}</span></div>
          {!!history.length && <label className="history-select">Open a saved draft<select value={plan?.id || ''} onChange={e => { if(e.target.value) run('load-plan', async () => { const result=await api<Plan>(`plans/${e.target.value}`); setPlan(result);setSaved(result.savedPath||'');setDay(result.date);setExplanation(''); }); }}><option value="">Choose a previous draft</option>{history.map(item=><option value={item.id} key={item.id}>{item.date} · {item.savedPath?'Markdown saved':'Local draft'} · {item.id.slice(0,6)}</option>)}</select></label>}
          {!plan ? <div className="empty-state"><div className="empty-icon"><CalendarDays size={28} aria-hidden="true" /></div><h3>Your notes are the starting point.</h3><p>Read your vault, choose a few tasks, and give them a realistic amount of time. Nothing is scheduled by assumption.</p><button className="button primary" disabled={!!busy} onClick={scanned ? () => setTab('sources') : scan}>{scanned ? 'Choose tasks' : 'Read my vault'}<ChevronRight size={17} aria-hidden="true" /></button></div> : <>
            {plan.calendarStale && <p className="message error">Outlook availability is stale or unavailable. This draft may conflict with recent events; refresh Outlook and rebuild before publishing.</p>}
            <div className="progress-summary"><p>{progress ? `${progress.completed} of ${progress.total} selected tasks completed in source notes.` : progressError || 'Checking source task progress…'}</p><button className="text-button" disabled={!!busy} onClick={refreshProgress}>Refresh progress</button></div>
            {progress && plan.blocks.some(block => progress.tasks[block.id]?.status !== 'open') && <p className="planning-help">This draft contains completed or unavailable source tasks. Build a new draft from open tasks before adding reminders or reviewing new Outlook changes. Existing calendar blocks remain unchanged.</p>}
            {!!deadlineWarnings.length && <section className="deadline-warnings" aria-label="Deadlines to review"><h3>Deadlines to review</h3><ul>{deadlineWarnings.map((warning, index) => <li key={`${warning.taskId}-${index}`}><strong>{[...plan.blocks, ...plan.unscheduled].find(task => task.id === warning.taskId)?.title}</strong><span>Due {warning.dueDate} · {warning.message}</span></li>)}</ul></section>}
            <ol className="blocks">{plan.blocks.map(block => <PlanTask key={block.id} block={block} progress={progress?.tasks[block.id]} busy={busy} vaultName={status?.vaultName || ''} complete={task => { setEditingTask(task); setCompletingTask(true); }} />)}</ol>
            {!plan.blocks.length && <p className="inline-empty">No selected tasks fit this date. Try another day or shorter estimates.</p>}
            {!!plan.unscheduled.length && <div className="overflow"><h3>Still in your inbox <span>{plan.unscheduled.length}</span></h3>{plan.unscheduled.map(task => <p key={task.id}><strong>{task.title}</strong><span>{task.reason}</span></p>)}</div>}
            <div className="plan-actions"><button className="button primary" disabled={!!busy || !!saved} onClick={() => run('save', async () => { const result = await api<{ path: string }>('plans/save', { planId: plan.id }); setSaved(result.path); setNotice('Saved a new Markdown plan. Existing source notes are unchanged.'); })}>{saved ? <Check size={16} aria-hidden="true" /> : <FileText size={16} aria-hidden="true" />}{saved ? 'Plan saved' : 'Save plan to Obsidian'}</button><button className="button secondary" disabled={!!busy || !status?.ollama.modelReady} onClick={() => run('ai', async () => { const result = await api<{ text: string }>('ai/explain', { planId: plan.id }); setExplanation(result.text); })}><Sparkles size={16} aria-hidden="true" />{busy === 'ai' ? 'Thinking locally…' : 'Explain with local AI'}</button></div>
            <PlanChange planId={plan.id} busy={busy} run={run} changed={next=>{setPlan(next);setSaved('');setNotice(`Rearranged ${next.change.movedCount} flexible tasks. ${next.unscheduled.length} remain unscheduled. Source notes and Outlook events are unchanged.`);api<{plans:{id:string;date:string;savedPath?:string}[]}>('plans').then(r=>setHistory(r.plans)).catch(()=>{});}} />
            <Publishing key={plan.id} planId={plan.id} hasBlocks={!!plan.blocks.length && !!progress && plan.blocks.every(block => progress.tasks[block.id]?.status === 'open')} status={status} busy={busy} run={run} notify={setNotice} />
            {saved && <p className="saved-path">{saved}</p>}{explanation && <div className="ai-note"><span className="eyebrow">LOCAL AI · DRAFT EXPLANATION</span><p>{explanation}</p></div>}
          </>}
        </section><aside className="day-context"><section className="panel"><div className="small-icon"><CalendarDays size={20} aria-hidden="true" /></div><h2>Your usual rhythm</h2><dl><div><dt>Work</dt><dd>Mon–Fri · 8 AM–5 PM</dd></div><div><dt>Personal</dt><dd>Every day · 6 AM–10 PM</dd></div><div><dt>Sleep protected</dt><dd>10 PM–6 AM</dd></div></dl><p className="muted-note">No fixed appointments or lunch break. Personal tasks stay outside work hours. Special dates need an explicit exception.</p></section><section className="panel quiet-panel"><ShieldCheck size={20} aria-hidden="true" /><h2>You stay in control.</h2><p>Reading notes changes nothing. Saving creates a separate plan. Source edits and Outlook writes need your approval.</p></section></aside></div>}
        {tab === 'sources' && <section className="panel source-panel"><div className="panel-heading"><div><h2>Task candidates <span className="subcount">{tasks.length}</span></h2><p>Unchecked boxes can be goals or examples. Select only what belongs in this plan.</p></div><span className="tag">{selected} selected</span></div><p className="planning-help">Type, estimate, priority and due-date choices are remembered when you build a draft. They do not edit your source notes. Inbox checkboxes select tasks; they do not mark them complete. Tasks due before/on the plan date get capacity first; within each group, priority and then earliest deadline determine order.</p><label className="search-label">Find a task<input type="search" placeholder="Search task or source note" value={filter} onChange={e => setFilter(e.target.value)} /></label>
          {!!scanWarnings.length && <details className="scan-warnings"><summary>Review {scanWarnings.length} scan warnings</summary><ul>{scanWarnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></details>}
          {!scanned ? <div className="inline-empty">Use “Read my vault” to discover your notes. No content has been loaded into this view yet.</div> : !filtered.length ? <div className="inline-empty">No matching task candidates.</div> : <div className="task-list">{filtered.map(task => <article className={`task-row ${choices[task.id] ? 'selected' : ''}`} key={task.id}><label className="task-pick"><input type="checkbox" checked={!!choices[task.id]} onChange={() => toggle(task.id)} /><span><strong>{task.title}</strong><span className="task-source">{task.source} · line {task.line}</span>{task.needsReview && <span className="review-label">Goal / backlog context — review before scheduling</span>}</span></label><button className="text-button edit-task-button" disabled={!!busy} onClick={()=>{setCompletingTask(false);setEditingTask(task);}}>Propose task edit</button>{choices[task.id] && <TaskOptions task={task} choice={choices[task.id]} change={change => updateChoice(task.id, change)} />}</article>)}</div>}
        </section>}
        {tab === 'connections' && <Connections status={status} busy={busy} day={day} run={run} onStatus={setStatus} notify={setNotice} />}
        {tab === 'reminders' && <Reminders busy={busy} run={run} notify={setNotice} />}
        <CapturePanel active={tab === 'capture'} busy={busy} run={run} notify={setNotice} onRecording={setRecording} />
        <footer className="workspace-footer"><span>Bej · built on DomoNote</span><span>{recording ? 'A manually started recording is active.' : 'Capture stays manual. Nothing is recording.'}</span></footer>
      </main>
    </div>
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
