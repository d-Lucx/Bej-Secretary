"""Private durable plans, settings, and reminder outbox."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from planner import MANILA, task_identity


class LocalStore:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'state.sqlite3'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, data TEXT NOT NULL, saved_path TEXT);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reminders(id TEXT PRIMARY KEY, task_key TEXT NOT NULL, channel TEXT NOT NULL,
                    due REAL NOT NULL, data TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt REAL NOT NULL, last_error TEXT, message_id TEXT);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT, action TEXT, detail TEXT);
                CREATE TABLE IF NOT EXISTS task_preferences(identity TEXT PRIMARY KEY, data TEXT NOT NULL);
            ''')
        self._upgrade_task_keys(directory)
        self._seed_task_ids()

    def _seed_task_ids(self):
        """Preserve legacy plan/calendar identities when source line numbers move."""
        if self.setting('tasks.stableIdsVersion') == 1:
            return
        with self.connect() as db:
            for row in db.execute('SELECT data FROM plans ORDER BY rowid').fetchall():
                for task in json.loads(row['data']).get('blocks', []):
                    identity = task_identity(task)
                    existing = db.execute('SELECT data FROM task_preferences WHERE identity=?', (identity,)).fetchone()
                    preference = json.loads(existing['data']) if existing else {}
                    if not preference.get('planTaskId'):
                        preference['planTaskId'] = task['id']
                        db.execute('INSERT INTO task_preferences VALUES(?,?) ON CONFLICT(identity) DO UPDATE SET data=excluded.data', (identity, json.dumps(preference)))
        self.set_setting('tasks.stableIdsVersion', 1)

    def _upgrade_task_keys(self, directory):
        if self.setting('reminders.taskKeysVersion') == 1:
            return
        # Preserve a recoverable SQLite snapshot before changing legacy keys.
        with self.connect() as db:
            rows = db.execute('SELECT id,data FROM reminders').fetchall()
            plans = {r['id']: json.loads(r['data']) for r in db.execute('SELECT id,data FROM plans')}
            if rows:
                backup_path = directory / 'reminders-before-task-keys.sqlite3'
                if not backup_path.exists():
                    with closing(sqlite3.connect(backup_path)) as backup:
                        db.backup(backup)
            for row in rows:
                payload = json.loads(row['data'])
                plan = plans.get(payload['planId'], {})
                block = next((b for b in plan.get('blocks', []) if b['id'] == payload['taskId']), None)
                if block:
                    identity = task_identity(block)
                    payload['sourceIdentity'] = identity
                    db.execute('UPDATE reminders SET task_key=?,data=? WHERE id=?',
                               (f"{payload['date']}:{identity}:" + db.execute('SELECT channel FROM reminders WHERE id=?', (row['id'],)).fetchone()['channel'], json.dumps(payload), row['id']))
            # Keep the latest queued revision; history is retained for review.
            db.execute("""UPDATE reminders SET state='canceled' WHERE state='pending' AND
                (rowid NOT IN (SELECT MAX(rowid) FROM reminders WHERE state='pending' GROUP BY task_key)
                 OR task_key IN (SELECT task_key FROM reminders WHERE state IN ('sending','sent','uncertain')))""")
        self.set_setting('reminders.taskKeysVersion', 1)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute('SELECT data FROM settings WHERE key=?', (key,)).fetchone()
            return json.loads(row['data']) if row else default

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data', (key, json.dumps(value)))

    def audit(self, action, detail):
        with self.connect() as db:
            db.execute('INSERT INTO audit(at,action,detail) VALUES(?,?,?)', (datetime.now(MANILA).isoformat(), action, json.dumps(detail)))

    def put_plan(self, plan, *, preferences=None):
        with self.connect() as db:
            db.execute('INSERT INTO plans(id,data) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (plan['id'], json.dumps(plan)))
            for identity, preference in (preferences or {}).items():
                db.execute('INSERT INTO task_preferences VALUES(?,?) ON CONFLICT(identity) DO UPDATE SET data=excluded.data',
                           (identity, json.dumps(preference)))

    def task_preferences(self):
        with self.connect() as db:
            return {r['identity']: json.loads(r['data']) for r in db.execute('SELECT * FROM task_preferences')}

    def task_id_aliases(self, day):
        aliases = {}
        with self.connect() as db:
            for row in db.execute("SELECT data FROM plans WHERE json_extract(data,'$.date')=?", (day,)):
                plan = json.loads(row['data'])
                for task in [*plan.get('blocks', []), *plan.get('unscheduled', [])]:
                    aliases.setdefault(task_identity(task), set()).add(task['id'])
        return aliases

    def reconcile_source_tasks(self, tasks, completed, *, complete_scan=True):
        active = {key for task in tasks for key in (task['id'], task_identity(task))}
        done = {key for task in completed for key in (task['id'], task_identity(task))} - active
        with self.connect() as db:
            for row in db.execute("SELECT id,data FROM reminders WHERE state='pending'").fetchall():
                payload = json.loads(row['data'])
                key = payload.get('sourceIdentity', payload['taskId'])
                if key not in active and (complete_scan or key in done):
                    reason = 'Source checkbox is complete.' if key in done else 'Source task is unavailable or changed. Review its source; completion has not been assumed.'
                    db.execute("UPDATE reminders SET state='canceled',last_error=? WHERE id=? AND state='pending'", (reason, row['id']))

    def get_plan(self, plan_id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM plans WHERE id=?', (plan_id,)).fetchone()
            return json.loads(row['data']) if row else None

    def list_plans(self):
        with self.connect() as db:
            rows = db.execute('SELECT id,data,saved_path FROM plans ORDER BY rowid DESC LIMIT 100').fetchall()
            return [{'id': r['id'], 'date': json.loads(r['data'])['date'], 'savedPath': r['saved_path']} for r in rows]

    def saved_path(self, plan_id):
        with self.connect() as db:
            row = db.execute('SELECT saved_path FROM plans WHERE id=?', (plan_id,)).fetchone()
            return row['saved_path'] if row else None

    def set_saved_path(self, plan_id, path):
        with self.connect() as db:
            db.execute('UPDATE plans SET saved_path=? WHERE id=?', (path, plan_id))

    def arm(self, plan, channel, now=None):
        if channel not in ('discord', 'desktop'):
            raise ValueError('Unknown reminder destination.')
        now = now or datetime.now(MANILA)
        result = []
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for block in plan['blocks']:
                due = datetime.fromisoformat(f"{plan['date']}T{block['start']}:00+08:00")
                task_key = f"{plan['date']}:{task_identity(block)}:{channel}"
                if db.execute("SELECT 1 FROM reminders WHERE task_key=? AND state IN ('sending','sent','uncertain')", (task_key,)).fetchone():
                    continue
                key = hashlib.sha256(f"{task_key}:{block['start']}".encode()).hexdigest()[:24]
                db.execute("UPDATE reminders SET state='canceled' WHERE task_key=? AND id<>? AND state='pending'", (task_key, key))
                payload = {'planId': plan['id'], 'taskId': block['id'], 'title': block['title'],
                           'sourceIdentity': task_identity(block),
                           'date': plan['date'], 'start': block['start'], 'end': block['end'], 'category': block['category']}
                state = 'pending' if due >= now else 'missed'
                db.execute('INSERT OR IGNORE INTO reminders(id,task_key,channel,due,data,state,next_attempt) VALUES(?,?,?,?,?,?,?)',
                           (key, task_key, channel, due.timestamp(), json.dumps(payload), state, due.timestamp()))
                db.execute("UPDATE reminders SET data=?,state=?,attempts=0,last_error=NULL,next_attempt=? WHERE id=? AND state IN ('pending','canceled','missed','failed')",
                           (json.dumps(payload), state, due.timestamp(), key))
                result.append(key)
        self.audit('reminders.armed', {'planId': plan['id'], 'channel': channel, 'count': len(result)})
        return result

    def disarm(self, plan_id, channel):
        if channel not in ('discord', 'desktop'):
            raise ValueError('Unknown reminder destination.')
        with self.connect() as db:
            cursor = db.execute("UPDATE reminders SET state='canceled' WHERE channel=? AND state='pending' AND json_extract(data,'$.planId')=?", (channel, plan_id))
            return cursor.rowcount

    def plan_reminder_counts(self, plan_id):
        with self.connect() as db:
            return {r['channel']: r['count'] for r in db.execute("SELECT channel,COUNT(*) AS count FROM reminders WHERE state='pending' AND json_extract(data,'$.planId')=? GROUP BY channel", (plan_id,))}

    def reminders(self):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM reminders ORDER BY due DESC LIMIT 250').fetchall()
            return [{**dict(r), 'data': json.loads(r['data'])} for r in rows]

    def recover_interrupted(self):
        with self.connect() as db:
            db.execute("UPDATE reminders SET state='uncertain', last_error='Service stopped during delivery. Check the destination before retrying.' WHERE state='sending'")

    def claim(self, now=None):
        now = (now or datetime.now(MANILA)).astimezone(MANILA)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE reminders SET state='missed',last_error='Reminder expired while unavailable.' WHERE state='pending' AND due<?", ((now - timedelta(minutes=30)).timestamp(),))
            if now.hour >= 22 or now.hour < 6:
                return None
            row = db.execute("SELECT * FROM reminders WHERE state='pending' AND next_attempt<=? AND due<=? ORDER BY due LIMIT 1", (now.timestamp(), now.timestamp())).fetchone()
            if not row:
                return None
            db.execute("UPDATE reminders SET state='sending',attempts=attempts+1 WHERE id=?", (row['id'],))
            return {**dict(row), 'data': json.loads(row['data']), 'attempts': row['attempts'] + 1}

    def finish(self, key, state, *, message_id=None, error=None, retry_after=None):
        if state not in ('sent', 'failed', 'uncertain', 'canceled', 'pending', 'missed'):
            raise ValueError('Invalid reminder state.')
        with self.connect() as db:
            db.execute('UPDATE reminders SET state=?,message_id=?,last_error=?,next_attempt=? WHERE id=?',
                       (state, message_id, error, (datetime.now(MANILA) + timedelta(seconds=retry_after or 0)).timestamp(), key))

    def cancel(self, key):
        with self.connect() as db:
            db.execute("UPDATE reminders SET state='canceled' WHERE id=? AND state='pending'", (key,))

    def release_paused(self, key):
        with self.connect() as db:
            db.execute("UPDATE reminders SET state='pending',attempts=MAX(0,attempts-1),next_attempt=? WHERE id=? AND state='sending'",
                       ((datetime.now(MANILA) + timedelta(seconds=30)).timestamp(), key))
