"""Read-only vault discovery and deterministic Manila-time daily planning."""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from planning_metadata import source_due, ranked_tasks, deadline_warnings

MANILA = timezone(timedelta(hours=8), 'Asia/Manila')
INTERNALS = {'.git', '.obsidian', '.copilot', 'bej plans'}
CHECKBOX = re.compile(r'^\s*[-*+]\s+\[ \]\s+(.+)$')
COMPLETED = re.compile(r'^\s*[-*+]\s+\[[xX]\]\s+(.+)$')


def generated_web_capture(source):
    return bool(re.fullmatch(r'bej captures/web/\d{4}-\d{2}-\d{2}-[a-f0-9]{32}\.md', source.casefold()))


def task_identity(task: dict) -> str:
    """A source task remains the same when surrounding lines move.

    Scope exact text to its note and heading: identical titles in different
    projects are not enough evidence to merge tasks.
    """
    if not task.get('source'):
        return task['id']
    title = ' '.join(task['title'].split()).casefold()
    return hashlib.sha256(f"{task['source']}\0{task.get('heading', '')}\0{title}".encode()).hexdigest()[:24]


def contained(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def linked(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def scan_vault(root: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('The configured vault is not a folder.')
    tasks, completed_tasks, warnings = [], [], []
    count = 0
    for parent, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(d for d in directories if d.lower() not in INTERNALS
                                and not linked(Path(parent) / d)
                                and contained(Path(parent) / d, root))
        for filename in sorted(files):
            path = Path(parent) / filename
            if path.suffix.lower() != '.md':
                continue
            if linked(path) or not contained(path, root):
                warnings.append('Skipped a linked note outside the supported source scope.')
                continue
            relative = path.relative_to(root).as_posix()
            if generated_web_capture(relative):
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    warnings.append(f'Skipped oversized note: {relative}')
                    continue
                raw = path.read_bytes()
                text = raw.decode('utf-8-sig')
            except (OSError, UnicodeError):
                warnings.append(f'Could not read UTF-8 note: {relative}')
                continue
            count += 1
            heading, fence = '', ''
            fingerprint = hashlib.sha256(raw).hexdigest()
            for line_number, line in enumerate(text.splitlines(), 1):
                stripped = line.lstrip()
                marker = re.match(r'^(`{3,}|~{3,})', stripped)
                if marker:
                    token = marker.group(1)
                    if not fence:
                        fence = token
                    elif token[0] == fence[0] and len(token) >= len(fence):
                        fence = ''
                    continue
                if fence:
                    continue
                if stripped.startswith('#'):
                    heading = stripped.lstrip('#').strip()
                unchecked = CHECKBOX.match(line)
                match = unchecked or COMPLETED.match(line)
                if not match:
                    continue
                title = match.group(1).strip()
                key = hashlib.sha256(f'{relative}\0{line_number}\0{title}'.encode()).hexdigest()[:24]
                destination = tasks if unchecked else completed_tasks
                destination.append({'id': key, 'title': title, 'source': relative, 'line': line_number,
                              'heading': heading, 'fingerprint': fingerprint,
                              **source_due(title),
                              'needsReview': bool(re.search(r'backlog|paused|template|example|milestone|goal|later|someday|roadmap', f'{relative} {heading}', re.I))})
    return {'tasks': tasks, 'completedTasks': completed_tasks, 'noteCount': count, 'warnings': warnings,
            'scannedAt': datetime.now(MANILA).isoformat()}


def make_plan(tasks: list[dict], day: str, capacity: int, now: datetime | None = None, *, busy: list[dict] | None = None, work_day_off: bool = False) -> dict:
    selected_day = date.fromisoformat(day)
    now = (now or datetime.now(MANILA)).astimezone(MANILA)
    if selected_day < now.date():
        raise ValueError('Choose today or a future date.')
    if type(capacity) is not int or not 15 <= capacity <= 960:
        raise ValueError('Daily task capacity must be 15–960 minutes.')
    ids, identities = set(), set()
    for task in tasks:
        if not task.get('id') or task['id'] in ids:
            raise ValueError('Select each task only once.')
        ids.add(task['id'])
        identity = task_identity(task)
        if identity in identities:
            raise ValueError('Select the same source task only once, even when repeated on another line.')
        identities.add(identity)
        if task.get('category') not in ('work', 'personal'):
            raise ValueError('Assign work or personal to each selected task.')
        if type(task.get('minutes')) is not int or not 5 <= task['minutes'] <= 480:
            raise ValueError('Task estimates must be 5–480 whole minutes.')
    tasks = ranked_tasks(tasks, selected_day.isoformat())
    weekday = selected_day.weekday() < 5 and not work_day_off
    earliest = now.hour * 60 + now.minute + (1 if now.second or now.microsecond else 0) if selected_day == now.date() else 0
    windows = {'work': [(480, 1020)] if weekday else [],
               'personal': [(360, 480), (1020, 1320)] if weekday else [(360, 1320)]}
    midnight = datetime.combine(selected_day, datetime.min.time(), MANILA)
    for event in busy or []:
        try:
            start_dt = datetime.fromisoformat(event['start'])
            end_dt = datetime.fromisoformat(event['end'])
            if start_dt.tzinfo is None or end_dt.tzinfo is None or end_dt <= start_dt:
                raise ValueError()
            start_minutes = max(0, int((start_dt - midnight).total_seconds() // 60))
            end_minutes = min(1440, int(((end_dt - midnight).total_seconds() + 59) // 60))
        except (KeyError, TypeError, ValueError):
            raise ValueError('Calendar availability contains an invalid event. Refresh Outlook before planning.') from None
        for kind, ranges in windows.items():
            remaining = []
            for start, end in ranges:
                if end_minutes <= start or start_minutes >= end:
                    remaining.append((start, end))
                else:
                    if start < start_minutes:
                        remaining.append((start, start_minutes))
                    if end_minutes < end:
                        remaining.append((end_minutes, end))
            windows[kind] = remaining
    cursors = {kind: [max(start, earliest) for start, _ in ranges] for kind, ranges in windows.items()}
    blocks, unscheduled, used = [], [], 0
    for task in tasks:
        kind, duration = task['category'], task['minutes']
        placed = False
        if used + duration <= capacity:
            for i, (_, end) in enumerate(windows[kind]):
                start = cursors[kind][i]
                if start + duration <= end:
                    blocks.append({**task, 'start': f'{start // 60:02}:{start % 60:02}',
                                   'end': f'{(start + duration) // 60:02}:{(start + duration) % 60:02}'})
                    cursors[kind][i] += duration
                    used += duration
                    placed = True
                    break
        if not placed:
            reason = 'Daily task capacity reached.' if used + duration > capacity else 'No remaining time in the applicable availability window.'
            unscheduled.append({**task, 'reason': reason})
    blocks.sort(key=lambda item: item['start'])
    return {'id': uuid.uuid4().hex, 'date': selected_day.isoformat(), 'timezone': 'Asia/Manila',
            'capacity': capacity, 'scheduledMinutes': used, 'blocks': blocks, 'unscheduled': unscheduled,
            'deadlineWarnings': deadline_warnings(blocks, unscheduled, selected_day.isoformat())}


def save_plan(root: Path, plan: dict) -> Path:
    root = root.resolve(strict=True)
    folder = root / 'Bej Plans'
    if linked(folder) or not contained(folder, root):
        raise ValueError('The plan folder must be an ordinary folder inside the vault.')
    folder.mkdir(exist_ok=True)
    if linked(folder) or not contained(folder, root):
        raise ValueError('The plan folder changed; no plan was saved.')
    day = date.fromisoformat(plan['date']).isoformat()
    content = [f'# Bej daily plan — {day}', '', 'Timezone: Asia/Manila (UTC+8)',
               'Draft generated from explicitly selected tasks. Source notes are unchanged.', '', '## Schedule', '']
    for block in plan['blocks']:
        title = block['title'].replace('\n', ' ')
        content.append(f"- [ ] {block['start']}–{block['end']} · {title} ({block['category']}, {block['minutes']} min)")
        content.append(f"  - Source: [[{block['source']}]] · line {block['line']}")
        content.append(f"  - Priority: {block.get('priority', 'normal')} · Due: {block.get('dueDate') or 'not specified'}")
    if not plan['blocks']:
        content.append('No tasks fit the selected availability and capacity.')
    if plan['unscheduled']:
        content.extend(['', '## Not scheduled', ''])
        for task in plan['unscheduled']:
            content.append(f"- {task['title']} — {task['reason']}")
    if plan.get('deadlineWarnings'):
        content.extend(['', '## Deadlines to review', ''])
        for warning in plan['deadlineWarnings']:
            task = next(item for item in [*plan['blocks'], *plan['unscheduled']] if item['id'] == warning['taskId'])
            content.append(f"- {task['title']} · due {warning['dueDate']}: {warning['message']}")
    target = folder / f'{day}-{uuid.uuid4().hex[:10]}.md'
    # Publish only complete files. Windows rename refuses an existing destination.
    descriptor, temporary = tempfile.mkstemp(prefix='.bej-', suffix='.tmp', dir=folder)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write('\n'.join(content) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == 'nt':
            os.rename(temporary, target)
        else:
            os.link(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target
