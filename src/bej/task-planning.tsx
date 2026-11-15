import React from 'react';
import { FileText } from 'lucide-react';
import { Block, Choice, Progress, Task } from './planning-types';

export function TaskOptions({ task, choice, change }: { task: Task; choice: Choice; change: (choice: Partial<Choice>) => void }) {
  return <div className="task-options">
    <label>Type<select value={choice.category} onChange={e => change({ category: e.target.value as Choice['category'] })}><option value="work">Work</option><option value="personal">Personal</option></select></label>
    <label>Minutes<input type="number" min={5} max={480} step={5} value={choice.minutes} onChange={e => change({ minutes: Number(e.target.value) })} /></label>
    <label>Priority<select value={choice.priority} onChange={e => change({ priority: e.target.value as Choice['priority'] })}><option value="urgent">Urgent</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option></select></label>
    <label>Due date <span className="hint">Optional · Manila date</span><input type="date" value={choice.dueDate || ''} onChange={e => change({ dueDate: e.target.value || null })} /></label>
    {(task.dueDate || task.dueWarning) && <p className="task-due-context">{task.dueDate && `Saved ${task.dueDateOrigin === 'local' ? 'local choice' : 'source due date'}: ${task.dueDate}. `}{task.dueWarning}</p>}
  </div>;
}

export function PlanTask({ block, progress, busy, vaultName, complete }: { block: Block; progress?: Progress['tasks'][string]; busy: string; vaultName: string; complete: (task: Task) => void }) {
  const source = progress?.task || block;
  return <li className={`block ${progress?.status === 'completed' ? 'task-completed' : ''}`}>
    <div className="block-time">{block.start}<span>{block.end}</span></div>
    <div className="block-detail"><div className="task-badges"><span className={`category ${block.category}`}>{block.category}</span>
      {block.priority && block.priority !== 'normal' && <span className={`tag priority-${block.priority}`}>{block.priority} priority</span>}
      {block.dueDate && <span className="tag">Due {block.dueDate}</span>}
      {progress?.status === 'completed' && <span className="tag">Completed in source</span>}
      {progress?.status === 'unavailable' && <span className="tag pending">Source unavailable or changed</span>}
    </div><h3>{block.title}</h3>
      <a className="source-link" href={`obsidian://open?vault=${encodeURIComponent(vaultName)}&file=${encodeURIComponent(source.source)}`}><FileText size={13} aria-hidden="true" />{source.source} · line {source.line}</a>
      <span className="duration">{block.minutes} min · flexible</span>
      {progress?.status === 'open' && progress.task && <button className="text-button" disabled={!!busy} onClick={() => complete(progress.task!)}>Review completion</button>}
      {progress?.status === 'unavailable' && <p className="source-status-note">Completion has not been assumed. Review the source before rebuilding.</p>}
    </div>
  </li>;
}
