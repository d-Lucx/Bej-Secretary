import unittest

import requests

from discord_adapter import DiscordAdapter, DiscordError


class Credentials:
    def __init__(self, token='fake-token'):
        self.token = token

    def get(self, name):
        assert name == 'discord-bot'
        return self.token


class Response:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self.data = data
        self.headers = {}

    def json(self):
        return self.data


class FakeHTTP:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.trust_env = True

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def valid_responses():
    return [Response(data={'id': '10', 'bot': True, 'username': 'Bej'}),
            Response(data={'id': '20', 'guild_id': '30', 'type': 0, 'name': 'reminders'})]


class DiscordAdapterTests(unittest.TestCase):
    def adapter(self, http, token='fake-token', guild='30', channel='20'):
        return DiscordAdapter(Credentials(token), guild, channel, http=http)

    def test_status_is_local_and_does_not_claim_delivery(self):
        http = FakeHTTP()
        self.assertEqual(self.adapter(http).status(), {
            'tokenStored': True, 'destinationConfigured': True, 'deliveryVerified': False})
        self.assertEqual(http.calls, [])

    def test_missing_credentials_never_contacts_discord(self):
        http = FakeHTTP()
        adapter = self.adapter(http, token=None)
        self.assertFalse(adapter.status()['tokenStored'])
        with self.assertRaises(DiscordError) as raised:
            adapter.send('Reminder', 'abc')
        self.assertTrue(raised.exception.permanent)
        self.assertEqual(http.calls, [])

    def test_validate_returns_only_safe_names(self):
        adapter = self.adapter(FakeHTTP(*valid_responses()))
        self.assertEqual(adapter.validate(), {'botName': 'Bej', 'channelName': 'reminders'})
        self.assertFalse(adapter.status()['deliveryVerified'])

    def test_wrong_guild_prevents_post(self):
        responses = valid_responses()
        responses[1].data['guild_id'] = '999'
        http = FakeHTTP(*responses)
        with self.assertRaises(DiscordError):
            self.adapter(http).send('Reminder', 'abc')
        self.assertEqual([c[0] for c in http.calls], ['GET', 'GET'])

    def test_nonbot_or_unsupported_channel_cannot_send(self):
        for field, value in [('bot', False), ('type', 1), ('id', '999')]:
            with self.subTest(field=field):
                responses = valid_responses()
                responses[0 if field == 'bot' else 1].data[field] = value
                http = FakeHTTP(*responses)
                with self.assertRaises(DiscordError):
                    self.adapter(http).send('Reminder', 'abc')
                self.assertNotIn('POST', [c[0] for c in http.calls])

    def test_send_disables_mentions_embeds_and_returns_id_with_nonce(self):
        http = FakeHTTP(*valid_responses(), Response(data={'id': '12345'}))
        adapter = self.adapter(http)
        self.assertEqual(adapter.send('@everyone Reminder https://example.com', 'queue-1'),
                         {'messageId': '12345'})
        self.assertTrue(adapter.status()['deliveryVerified'])
        method, url, options = http.calls[-1]
        self.assertEqual((method, url), ('POST', 'https://discord.com/api/v10/channels/20/messages'))
        self.assertEqual(options['json'], {
            'content': '@everyone Reminder https://example.com', 'nonce': 'queue-1',
            'enforce_nonce': True, 'allowed_mentions': {'parse': []}, 'flags': 4})
        self.assertFalse(http.trust_env)
        for _, url, options in http.calls:
            self.assertTrue(url.startswith('https://discord.com/api/v10/'))
            self.assertFalse(options['allow_redirects'])
            self.assertEqual(options['timeout'], (5, 20))

    def test_every_send_revalidates_destination(self):
        responses = valid_responses()
        responses[1].data['guild_id'] = '999'
        http = FakeHTTP(*valid_responses(), Response(data={'id': '12345'}), *responses)
        adapter = self.adapter(http)
        adapter.send('First', 'one')
        with self.assertRaises(DiscordError):
            adapter.send('Second', 'two')
        self.assertEqual(len([c for c in http.calls if c[0] == 'POST']), 1)

    def test_invalid_content_nonce_or_ids_never_contact_discord(self):
        for content, nonce in [('', 'a'), ('x' * 2001, 'a'), ({'attachments': []}, 'a'),
                               ('ok', ''), ('ok', 'n' * 26), ('ok', 123)]:
            with self.subTest(content_type=type(content), nonce=nonce):
                http = FakeHTTP()
                with self.assertRaises(DiscordError):
                    self.adapter(http).send(content, nonce)
                self.assertEqual(http.calls, [])
        http = FakeHTTP()
        with self.assertRaises(DiscordError):
            self.adapter(http, channel='../elsewhere').send('ok', 'a')
        self.assertEqual(http.calls, [])

    def test_rate_limit_provides_retry_delay_without_retry_or_body_leak(self):
        http = FakeHTTP(*valid_responses(), Response(429, {'retry_after': 1.25, 'message': 'secret'}))
        with self.assertRaises(DiscordError) as raised:
            self.adapter(http).send('private reminder', 'abc')
        self.assertEqual(raised.exception.retry_after, 1.25)
        self.assertFalse(raised.exception.uncertain)
        self.assertFalse(raised.exception.permanent)
        self.assertNotIn('secret', str(raised.exception))
        self.assertEqual(len(http.calls), 3)

    def test_post_timeout_is_uncertain_and_redacted_without_retry(self):
        http = FakeHTTP(*valid_responses(), requests.Timeout('fake-token private reminder'))
        with self.assertRaises(DiscordError) as raised:
            self.adapter(http).send('private reminder', 'abc')
        self.assertTrue(raised.exception.uncertain)
        self.assertNotIn('fake-token', str(raised.exception))
        self.assertEqual(len(http.calls), 3)

    def test_read_timeout_is_safe_to_retry(self):
        with self.assertRaises(DiscordError) as raised:
            self.adapter(FakeHTTP(requests.Timeout('sensitive'))).validate()
        self.assertFalse(raised.exception.uncertain)

    def test_http_errors_are_actionable_and_redacted(self):
        for code in [401, 403, 404, 302, 500]:
            with self.subTest(code=code):
                http = FakeHTTP(Response(code, {'message': 'fake-token sensitive body'}))
                with self.assertRaises(DiscordError) as raised:
                    self.adapter(http).validate()
                self.assertNotIn('fake-token', str(raised.exception))
                self.assertNotIn('sensitive', str(raised.exception))
                self.assertEqual(raised.exception.permanent, code < 500)

    def test_malformed_success_after_post_is_uncertain(self):
        http = FakeHTTP(*valid_responses(), Response(data={}))
        with self.assertRaises(DiscordError) as raised:
            self.adapter(http).send('Reminder', 'abc')
        self.assertTrue(raised.exception.uncertain)

    def test_generic_test_message_has_no_task_details(self):
        http = FakeHTTP(*valid_responses(), Response(data={'id': '12345'}))
        adapter = self.adapter(http)
        self.assertEqual(adapter.test_message(), {'messageId': '12345'})
        self.assertEqual(http.calls[-1][2]['json']['content'], 'Bej Secretary: Discord connection test.')


if __name__ == '__main__':
    unittest.main()
