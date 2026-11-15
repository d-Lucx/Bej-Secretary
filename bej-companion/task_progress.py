"""Source-backed progress; disappearance never proves completion."""
from planner import task_identity


def plan_progress(plan, snapshot):
    current = {task_identity(task): task for task in snapshot['tasks']}
    completed = {task_identity(task) for task in snapshot.get('completedTasks', [])}
    result = {}
    for task in [*plan['blocks'], *plan.get('unscheduled', [])]:
        identity = task_identity(task)
        if identity in current:
            result[task['id']] = {'status': 'open', 'task': current[identity]}
        else:
            result[task['id']] = {'status': 'completed' if identity in completed else 'unavailable'}
    return {'planId': plan['id'], 'tasks': result, 'total': len(result),
            'completed': sum(row['status'] == 'completed' for row in result.values()),
            'warnings': snapshot.get('warnings', [])}
