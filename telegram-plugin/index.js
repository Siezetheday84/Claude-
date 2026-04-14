#!/usr/bin/env node
/**
 * Claude Telegram Plugin — MCP Server (Grammy edition)
 *
 * Exposes Telegram messaging capabilities to Claude Code via the
 * Model Context Protocol (MCP). Claude can send messages, fetch
 * recent chat history, and list known chats through this server.
 *
 * Setup:
 *   1. Copy .env.example to .env and fill in your TELEGRAM_BOT_TOKEN
 *   2. npm install
 *   3. Register in .claude/settings.json (see project root)
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { Bot } from "grammy";
import { readFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load .env if present
const envPath = resolve(__dirname, ".env");
if (existsSync(envPath)) {
  const lines = readFileSync(envPath, "utf8").split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim();
    if (key && !(key in process.env)) process.env[key] = val;
  }
}

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
if (!BOT_TOKEN) {
  console.error(
    "Error: TELEGRAM_BOT_TOKEN is not set.\n" +
      "Copy telegram-plugin/.env.example to telegram-plugin/.env and add your token."
  );
  process.exit(1);
}

const ALLOWED_CHAT_IDS = process.env.TELEGRAM_ALLOWED_CHAT_IDS
  ? new Set(process.env.TELEGRAM_ALLOWED_CHAT_IDS.split(",").map((s) => s.trim()))
  : null;

// --- Bot setup (Grammy) ---
const bot = new Bot(BOT_TOKEN);

/** @type {Map<string, {id: number, type: string, title: string, username?: string, messages: Array}>} */
const knownChats = new Map();
const MAX_HISTORY = 50;

bot.on("message", (ctx) => {
  const chatId = String(ctx.chat.id);
  if (ALLOWED_CHAT_IDS && !ALLOWED_CHAT_IDS.has(chatId)) return;

  if (!knownChats.has(chatId)) {
    const c = ctx.chat;
    const title =
      c.type === "private"
        ? [c.first_name, c.last_name].filter(Boolean).join(" ")
        : c.title ?? c.username ?? chatId;
    knownChats.set(chatId, {
      id: c.id,
      type: c.type,
      title,
      username: "username" in c ? c.username : undefined,
      messages: [],
    });
  }

  const chat = knownChats.get(chatId);
  chat.messages.push({
    messageId: ctx.message.message_id,
    from: ctx.from?.username ?? ctx.from?.first_name ?? "unknown",
    text: ctx.message.text ?? "[non-text]",
    date: new Date(ctx.message.date * 1000).toISOString(),
  });

  if (chat.messages.length > MAX_HISTORY) {
    chat.messages.splice(0, chat.messages.length - MAX_HISTORY);
  }
});

// Start long-polling in background (errors are logged, not fatal)
bot.start({ drop_pending_updates: true }).catch((err) => {
  console.error("Bot polling error:", err.message);
});

// --- MCP Server ---
const server = new McpServer({
  name: "telegram",
  version: "1.0.0",
});

server.tool(
  "send_message",
  "Send a Telegram message to a chat",
  {
    chat_id: z.union([z.string(), z.number()]).describe("Telegram chat ID or @username"),
    text: z.string().min(1).max(4096).describe("Message text (Markdown supported)"),
    parse_mode: z
      .enum(["Markdown", "MarkdownV2", "HTML"])
      .optional()
      .describe("Optional parse mode for formatting"),
  },
  async ({ chat_id, text, parse_mode }) => {
    try {
      const sent = await bot.api.sendMessage(chat_id, text, parse_mode ? { parse_mode } : {});
      return {
        content: [
          {
            type: "text",
            text: `Message sent. message_id=${sent.message_id}, chat_id=${sent.chat.id}`,
          },
        ],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Failed to send message: ${err.message}` }],
        isError: true,
      };
    }
  }
);

server.tool(
  "get_messages",
  "Get recent messages from a Telegram chat (buffered since bot started)",
  {
    chat_id: z.string().describe("Telegram chat ID"),
    limit: z
      .number()
      .int()
      .min(1)
      .max(MAX_HISTORY)
      .optional()
      .describe("Max messages to return (default 20)"),
  },
  async ({ chat_id, limit = 20 }) => {
    const chat = knownChats.get(String(chat_id));
    if (!chat) {
      return {
        content: [
          {
            type: "text",
            text: `No messages buffered for chat ${chat_id}. Ensure the bot has received messages in this chat.`,
          },
        ],
      };
    }
    const msgs = chat.messages.slice(-limit);
    return {
      content: [{ type: "text", text: JSON.stringify(msgs, null, 2) }],
    };
  }
);

server.tool(
  "list_chats",
  "List all Telegram chats the bot has seen since it started",
  {},
  async () => {
    if (knownChats.size === 0) {
      return {
        content: [
          {
            type: "text",
            text: "No chats seen yet. Send a message to the bot first.",
          },
        ],
      };
    }
    const summary = [...knownChats.values()].map(({ id, type, title, username, messages }) => ({
      id,
      type,
      title,
      username,
      messageCount: messages.length,
    }));
    return {
      content: [{ type: "text", text: JSON.stringify(summary, null, 2) }],
    };
  }
);

server.tool(
  "get_bot_info",
  "Get information about the connected Telegram bot",
  {},
  async () => {
    try {
      const me = await bot.api.getMe();
      return {
        content: [{ type: "text", text: JSON.stringify(me, null, 2) }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Failed to get bot info: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// --- Start MCP transport ---
const transport = new StdioServerTransport();
await server.connect(transport);
