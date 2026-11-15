"""Narrow outbound-only Discord transport; never retries or reads channel history."""

import math
import re
import uuid

import requests


class DiscordError(Exception):
    """Safe, user-facing failure with queue scheduling information."""

    def __init__(self, message, *, retry_after=None, uncertain=False, permanent=False):
        super().__init__(message)
        self.retry_after = retry_after
        self.uncertain = uncertain
        self.permanent = permanent


class DiscordAdapter:
    API = 'https://discord.com/api/v10'

    def __init__(self, credential_store, guild_id: str, channel_id: str, *, http=None):
        self.credential_store = credential_store
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.http = http if http is not None else requests.Session()
        self.http.trust_env = False
        self._delivery_verified = False

    @staticmethod
    def _valid_id(value):
        return isinstance(value, str) and re.fullmatch(r'[0-9]{1,20}', value) is not None

    def _token(self):
        try:
            token = self.credential_store.get('discord-bot')
        except Exception:
            raise DiscordError('Unable to read the Discord bot credential. Check Windows Credentials.',
                               permanent=True) from None
        if not isinstance(token, str) or not token.strip():
            raise DiscordError('Store a Discord bot token in Windows Credentials first.',
                               permanent=True)
        return token

    def status(self):
        try:
            stored = bool(self._token())
        except DiscordError:
            stored = False
        return {'tokenStored': stored,
                'destinationConfigured': self._valid_id(self.guild_id) and self._valid_id(self.channel_id),
                'deliveryVerified': self._delivery_verified and stored}

    def _request(self, method, path, token, *, payload=None):
        options = {'headers': {'Authorization': 'Bot ' + token},
                   'timeout': (5, 20), 'allow_redirects': False}
        if payload is not None:
            options['json'] = payload
        try:
            response = self.http.request(method, self.API + path, **options)
        except requests.RequestException:
            raise DiscordError('Discord could not be reached. Check your connection.',
                               uncertain=method == 'POST') from None
        code = response.status_code
        if code == 429:
            delay = None
            try:
                raw = response.json().get('retry_after')
                if not isinstance(raw, bool):
                    value = float(raw)
                    if math.isfinite(value) and value >= 0:
                        delay = value
            except (ValueError, TypeError, AttributeError):
                pass
            raise DiscordError('Discord rate limit reached. Delivery will wait before retrying.',
                               retry_after=delay)
        if code == 401:
            raise DiscordError('Discord rejected the bot token. Replace it in Windows Credentials.',
                               permanent=True)
        if code == 403:
            raise DiscordError('Discord denied access. Give the bot View Channel and Send Messages permissions.',
                               permanent=True)
        if not 200 <= code < 300:
            raise DiscordError('Discord rejected the request. Check the configured bot and channel.',
                               permanent=code < 500, uncertain=method == 'POST' and code >= 500)
        try:
            data = response.json()
        except (ValueError, TypeError):
            raise DiscordError('Discord returned an unreadable response.',
                               uncertain=method == 'POST') from None
        if not isinstance(data, dict):
            raise DiscordError('Discord returned an unexpected response.', uncertain=method == 'POST')
        return data

    @staticmethod
    def _safe_name(value, token):
        if not isinstance(value, str):
            return ''
        # Names are display-only. Do not expose controls or a credential echoed by a response.
        return ''.join(char for char in value.replace(token, '[redacted]') if char.isprintable())[:100]

    def _validate(self, token):
        if not self._valid_id(self.guild_id) or not self._valid_id(self.channel_id):
            raise DiscordError('Configure valid Discord server and channel IDs first.', permanent=True)
        bot = self._request('GET', '/users/@me', token)
        if bot.get('bot') is not True:
            raise DiscordError('The stored Discord credential must belong to a bot.', permanent=True)
        channel = self._request('GET', '/channels/' + self.channel_id, token)
        if (channel.get('guild_id') != self.guild_id or channel.get('id') != self.channel_id
                or type(channel.get('type')) is not int or channel['type'] not in (0, 5)):
            raise DiscordError('The Discord channel must be a text channel in the configured server.',
                               permanent=True)
        return {'botName': self._safe_name(bot.get('username'), token),
                'channelName': self._safe_name(channel.get('name'), token)}

    def validate(self):
        return self._validate(self._token())

    def send(self, content: str, nonce: str):
        if not isinstance(content, str) or not content.strip() or len(content) > 2000:
            raise DiscordError('Discord messages must contain 1 to 2000 characters.', permanent=True)
        if not isinstance(nonce, str) or not nonce.strip() or len(nonce) > 25:
            raise DiscordError('Discord delivery requires a stable nonce of 1 to 25 characters.', permanent=True)
        token = self._token()
        self._validate(token)
        result = self._request('POST', '/channels/' + self.channel_id + '/messages', token,
                               payload={'content': content, 'allowed_mentions': {'parse': []},
                                        'flags': 4, 'nonce': nonce, 'enforce_nonce': True})
        message_id = result.get('id')
        if not self._valid_id(message_id):
            raise DiscordError('Discord did not confirm a message ID. Check delivery before retrying.',
                               uncertain=True)
        self._delivery_verified = True
        return {'messageId': message_id}

    def test_message(self):
        """Explicitly invoked by the user-facing connection-test action only."""
        return self.send('Bej Secretary: Discord connection test.', uuid.uuid4().hex[:25])
