"""Explicit unavailable-window changes produce a fresh local flexible-task draft."""
from datetime import datetime

from planner import make_plan


def reflow_plan(plan, start, end, reason, *, busy=None, work_day_off=False, now=None):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 160:
        raise ValueError('Describe this availability change in 1–160 characters.')
    try:
        start_dt = datetime.fromisoformat(f"{plan['date']}T{start}:00+08:00")
        end_dt = datetime.fromisoformat(f"{plan['date']}T{end}:00+08:00")
        if end_dt <= start_dt:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('Choose an unavailable window ending after it starts.') from None
    combined = [*plan['blocks'], *plan['unscheduled']]
    tasks = []
    seen = set()
    for task in combined:
        if task['id'] not in seen:
            tasks.append(task)
            seen.add(task['id'])
    blocked = {'start': start_dt.isoformat(), 'end': end_dt.isoformat()}
    result = make_plan(tasks, plan['date'], plan['capacity'], now, busy=[*(busy or []), blocked], work_day_off=work_day_off)
    previous = {task['id']: (task['start'], task['end']) for task in plan['blocks']}
    moved = [task['id'] for task in result['blocks'] if previous.get(task['id']) != (task['start'], task['end'])]
    result['change'] = {'previousPlanId': plan['id'], 'reason': reason.strip(), 'unavailable': blocked, 'movedCount': len(moved)}
    return result
