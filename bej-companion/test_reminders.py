import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from discord_adapter import DiscordError
from planner import MANILA
from reminders import ReminderWorker, carry_forward_reminders
from state import LocalStore


class FakeDiscord:
    def __init__(self, error=None):
        self.error = error
        self.sent = []
    def send(self, content, nonce):
        self.sent.append((content, nonce))
        if self.error:
            raise self.error
        return {'messageId': '123'}


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.tmp.name))
        self.now = datetime(2026, 11, 16, 8, 0, tzinfo=MANILA)
        self.plan = {'id': 'p', 'date': '2026-11-16', 'blocks': [{'id': 't', 'title': 'Review @everyone', 'start': '08:00', 'end': '08:30', 'category': 'work'}]}
        self.store.arm(self.plan, 'discord', self.now - timedelta(minutes=5))
        self.store.set_setting('discord.enabled', True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_confirmed_delivery_is_durable_and_not_repeated(self):
        adapter = FakeDiscord()
        worker = ReminderWorker(self.store, adapter)
        worker.tick(self.now)
        worker.tick(self.now)
        self.assertEqual(len(adapter.sent), 1)
        self.assertEqual(self.store.reminders()[0]['state'], 'sent')
        self.assertEqual(self.store.reminders()[0]['message_id'], '123')

    def test_uncertain_send_is_not_blindly_retried(self):
        adapter = FakeDiscord(DiscordError('Timed out', uncertain=True))
        worker = ReminderWorker(self.store, adapter)
        worker.tick(self.now)
        worker.tick(self.now)
        self.assertEqual(len(adapter.sent), 1)
        self.assertEqual(self.store.reminders()[0]['state'], 'uncertain')

    def test_rate_limit_returns_to_pending_with_delay(self):
        adapter = FakeDiscord(DiscordError('Wait', retry_after=60))
        ReminderWorker(self.store, adapter).tick(self.now)
        item = self.store.reminders()[0]
        self.assertEqual(item['state'], 'pending')
        self.assertEqual(item['attempts'], 1)

    def test_disabled_channel_stays_pending_without_sending(self):
        self.store.set_setting('discord.enabled', False)
        adapter = FakeDiscord()
        ReminderWorker(self.store, adapter).tick(self.now)
        self.assertEqual(adapter.sent, [])
        self.assertEqual(self.store.reminders()[0]['state'], 'pending')

    def test_completed_or_removed_source_task_is_not_sent(self):
        adapter = FakeDiscord()
        ReminderWorker(self.store, adapter, task_is_current=lambda _task_id: False).tick(self.now)
        self.assertEqual(adapter.sent, [])
        self.assertEqual(self.store.reminders()[0]['state'], 'canceled')

    def test_reflow_keeps_individually_canceled_tasks_disabled(self):
        future = (datetime.now(MANILA) + timedelta(days=2)).date().isoformat()
        original = {'id': 'original', 'date': future, 'blocks': [
            {'id': 'a', 'title': 'A', 'start': '08:00', 'end': '08:30', 'category': 'work'},
            {'id': 'b', 'title': 'B', 'start': '08:30', 'end': '09:00', 'category': 'work'}]}
        self.store.arm(original, 'discord')
        b = next(item for item in self.store.reminders() if item['data']['taskId'] == 'b')
        self.store.cancel(b['id'])
        changed = {'id': 'changed', 'date': future, 'blocks': [
            {**original['blocks'][0], 'start': '09:00', 'end': '09:30'},
            {**original['blocks'][1], 'start': '09:30', 'end': '10:00'},
            {'id': 'never-armed', 'title': 'C', 'start': '10:00', 'end': '10:30', 'category': 'work'}]}
        carry_forward_reminders(self.store, 'original', changed)
        pending = [item['data']['taskId'] for item in self.store.reminders() if item['state'] == 'pending']
        self.assertEqual(set(pending), {'a', 't'})  # Unrelated pre-existing reminder is preserved.


if __name__ == '__main__':
    unittest.main()
