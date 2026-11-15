"""Durable reminder dispatcher: explicit arming, quiet hours, bounded retries."""
import threading
from datetime import datetime

from discord_adapter import DiscordError
from planner import MANILA


def carry_forward_reminders(store, previous_plan_id, plan):
    """Retain pending per-task consent, including deliberate individual cancellations."""
    pending = [item for item in store.reminders()
               if item['data'].get('planId') == previous_plan_id and item['state'] == 'pending']
    choices = {}
    for item in pending:
        choices.setdefault(item['channel'], set()).add(item['data']['taskId'])
        store.cancel(item['id'])
    for channel, task_ids in choices.items():
        selected = {**plan, 'blocks': [block for block in plan['blocks'] if block['id'] in task_ids]}
        store.arm(selected, channel)


class ReminderWorker:
    def __init__(self, store, discord, desktop=None, task_is_current=None):
        self.store = store
        self.discord = discord
        self.desktop = desktop
        self.task_is_current = task_is_current
        self.stop_event = threading.Event()
        self.thread = None

    def tick(self, now=None):
        now = now or datetime.now(MANILA)
        item = self.store.claim(now)
        if not item:
            return
        if not self.store.setting(f"{item['channel']}.enabled", False):
            self.store.release_paused(item['id'])
            return
        data = item['data']
        if self.task_is_current:
            try:
                if not self.task_is_current(data.get('sourceIdentity', data['taskId'])):
                    self.store.finish(item['id'], 'canceled', error='The source task was completed, removed, or changed. Rescan before arming it again.')
                    return
            except Exception:
                self.store.release_paused(item['id'])
                return
        content = f"Bej reminder · {data['date']} {data['start']}–{data['end']} (Manila, UTC+8)\n{data['title']}"
        try:
            if item['channel'] == 'discord':
                result = self.discord.send(content[:2000], item['id'])
            elif self.desktop:
                result = self.desktop.notify('Bej reminder', content[:1000])
            else:
                raise DiscordError('Desktop reminders are unavailable.', permanent=True)
            self.store.finish(item['id'], 'sent', message_id=result.get('messageId', 'desktop'))
        except DiscordError as error:
            state = 'uncertain' if error.uncertain else 'failed' if error.permanent or item['attempts'] >= 3 else 'pending'
            self.store.finish(item['id'], state, error=str(error), retry_after=max(15, min(error.retry_after or 60, 3600)))
        except Exception:
            self.store.finish(item['id'], 'uncertain', error='Delivery was interrupted. Check the destination before retrying.')

    def start(self):
        self.store.recover_interrupted()
        def loop():
            while not self.stop_event.is_set():
                try:
                    self.tick()
                except Exception:
                    # Do not include private content, credentials, or raw transport errors in logs.
                    self.store.set_setting('reminderWorkerError', 'The reminder worker encountered an error. Review the queue.')
                self.stop_event.wait(5)
        self.thread = threading.Thread(target=loop, name='bej-reminders', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
