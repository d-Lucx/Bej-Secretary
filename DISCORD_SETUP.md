# Set up Bej in your private Discord bot channel

Status: bot credential and destination are configured locally. The explicitly approved generic live test was delivered successfully. Scheduled delivery is implemented through Bej's persistent reminder queue; no personal tasks are armed by setup alone.

Launch **Start-Bej.cmd**, build a draft, then use **Enable Discord reminders for this plan**. The reminder queue persists across restarts, respects 10 PM–6 AM quiet hours, and reports failed/uncertain/missed sends honestly. Use **Connections** to validate access or replace the token in Windows Credential Manager. Never paste the token in chat, Git, or Obsidian.

## Choose the connection

The proposed path is a dedicated **Bej bot**, allowing reminders now and commands later. An incoming webhook is simpler if you only want outbound reminders; it does not need a bot user. You do not need both. [Discord webhook reference](https://docs.discord.com/developers/resources/webhook)

## Prepare the bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications), choose **New Application**, and name it **Bej Assistant**.
2. Open **Bot**. Under **Token**, use **Reset Token** to generate the credential. Store it privately in a password manager for now; the planned Bej runtime will use Windows credential storage. Never paste it into this chat, Obsidian, Git, or a screenshot.
3. Under **Installation**, enable **Guild Install** for your server. Choose a Discord-provided install link. In the guild install settings, select the `bot` scope; add `applications.commands` if preparing for later slash commands.
4. Request only **View Channels**, **Send Messages**, and optionally **Embed Links** for formatted reminders. Leave Administrator and privileged intents off for the reminders-only design.
5. Use the generated install link, select your existing private server, and authorize the bot. Your account needs permission to install apps there.

The application, token, installation, and scope workflow is described in [Discord's official bot setup guide](https://docs.discord.com/developers/quick-start/getting-started). These permissions are Bej's proposed minimal reminder configuration, not a requirement to grant broad server access.

## Give it access to your existing private channel

Open the channel's **Edit Channel → Permissions**. Allow the Bej bot or its role to view the channel and send messages, and allow embeds if selected above. Check that category permissions do not block those actions. Keep access limited to the intended channel. Other bots that already have access may see reminders too.

In Discord **User Settings → Advanced**, turn on **Developer Mode**. Then copy and keep these identifiers locally:

- Server ID: right-click the server icon → **Copy Server ID**.
- Channel ID: right-click your bot channel → **Copy Channel ID**.
- Your user ID: right-click your user → **Copy User ID**; needed if commands are enabled later.
- Application ID: available in the Developer Portal's **General Information** page.

These IDs identify the destination; the bot token is the secret. [Discord's official ID guide](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID)

## Connect and arm reminders

Launch **Start-Bej.cmd** and open **Connections**. Enter the bot token into the password field and choose **Save token locally**. The backend uses Windows Credential Manager and will report an error rather than fall back to plaintext storage. The nonsecret server/channel IDs are already in local configuration. Saving the token does not enable scheduled messaging; explicitly arm a plan after reviewing it.

For outbound reminders, the local process can use Discord's HTTP API. If slash commands are added, a Gateway connection lets the laptop receive Discord events over an outbound WebSocket; that design does not need a public web server or tunnel to the vault. This is the proposed Bej architecture, based on [Discord's Gateway documentation](https://docs.discord.com/developers/events/gateway).

Only task names and reminder details are permitted for Discord. Keep notes, recordings, screenshots, credentials, and attachments local. The laptop must be awake, online, and running the adapter to deliver scheduled reminders; desktop planning remains available offline.

After connecting, explicitly trigger one generic test from the local app, confirm it reaches only the configured channel, and verify that the app reports failures accurately. No test message has been sent by this setup guide. Commands, if added, must validate your user ID and the configured server/channel before taking action; bot installation alone must not grant other channel members control of Bej.

## If you prefer a webhook for reminders only

In **Server Settings → Integrations → Webhooks**, create one named **Bej**, select your existing bot channel, and copy its URL into private local secret storage when the adapter supports it. The URL contains the posting credential; treat it like a password. Do not commit it or paste it into chat. [Discord's official webhook setup instructions](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)

This path can post reminders but is not a bot that reads or answers channel messages. Use the bot path above if interactive commands are part of the agreed release.
