# Claude-

A Claude Code project with a Telegram plugin — integrates Telegram messaging into Claude via an MCP server.

## Telegram Plugin

Enables Claude Code to send messages, read chat history, and list known chats through a Telegram bot.

### Setup

1. **Create a bot** via [@BotFather](https://t.me/BotFather) on Telegram to get a bot token.

2. **Configure the environment:**
   ```bash
   cp telegram-plugin/.env.example telegram-plugin/.env
   # Edit telegram-plugin/.env and set TELEGRAM_BOT_TOKEN=<your token>
   ```

3. **Install dependencies:**
   ```bash
   cd telegram-plugin && npm install
   ```

4. **Start Claude Code** — it will auto-launch the MCP server from `.claude/settings.json`.
   Alternatively, export the token before starting:
   ```bash
   export TELEGRAM_BOT_TOKEN=<your token>
   claude
   ```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `send_message` | Send a message to any Telegram chat |
| `get_messages` | Retrieve buffered recent messages from a chat |
| `list_chats` | List all chats the bot has seen since startup |
| `get_bot_info` | Show info about the connected bot account |

### Restricting Access

Set `TELEGRAM_ALLOWED_CHAT_IDS` in `.env` to a comma-separated list of chat IDs to restrict which chats the plugin processes:

```
TELEGRAM_ALLOWED_CHAT_IDS=123456789,987654321
```
