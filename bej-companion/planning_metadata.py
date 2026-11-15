"""Explicit task-line metadata and deterministic allocation order. No inference."""
import re
from datetime import date

PRIORITIES = {'urgent': 0, 'high': 1, 'normal': 2, 'low': 3}


def valid_due(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Due dates must be a real YYYY-MM-DD date, or left blank.')
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError('Due dates must be a real YYYY-MM-DD date, or left blank.') from None
    return value


def source_due(title):
    markers = re.findall(r'(?:📅|\bdue::)\s*(\S*)', title)
    if not markers:
        return {'dueDate': None}
    try:
        dates = {valid_due(value) for value in markers}
        if len(dates) != 1:
            raise ValueError()
        return {'dueDate': dates.pop()}
    except ValueError:
        return {'dueDate': None, 'dueWarning': 'Due markers are invalid or conflicting. Choose a date explicitly before relying on a deadline.'}


def ranked_tasks(tasks, day):
    for task in tasks:
        if task.get('priority', 'normal') not in PRIORITIES:
            raise ValueError('Choose urgent, high, normal or low priority.')
        valid_due(task.get('dueDate'))

    def key(task):
        due = task.get('dueDate')
        group = 0 if due and due < day else 1 if due == day else 2
        return group, PRIORITIES[task.get('priority', 'normal')], due or '9999-12-31'

    return sorted(tasks, key=key)  # Stable sort retains selection order on ties.


def deadline_warnings(blocks, unscheduled, day):
    warnings = {}
    for task in [*blocks, *unscheduled]:
        due = task.get('dueDate')
        if due and due < day:
            warnings[task['id']] = {'taskId': task['id'], 'dueDate': due, 'message': 'Due before this plan date. Review the deadline; Bej has not changed it.'}
    for task in unscheduled:
        due = task.get('dueDate')
        if due and due <= day:
            previous = warnings.get(task['id'], {}).get('message', '')
            warnings[task['id']] = {'taskId': task['id'], 'dueDate': due, 'message': (previous + ' This due task could not fit. Reduce scope or explicitly choose another plan; its deadline is unchanged.').strip()}
    return list(warnings.values())
