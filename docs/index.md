# Local Pigeon Documentation

**Local Pigeon** is a privacy-first AI assistant that runs entirely on your machine. It pairs a local LLM (via [Ollama](https://ollama.com)) with a rich set of built-in tools—web search, file management, code execution, scheduling, and more—all accessible through a polished web UI, Discord, Telegram, or the CLI.

## Quick Links

| Topic | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Install, configure, and launch Local Pigeon |
| [Troubleshooting](troubleshooting.md) | Common issues and `botf doctor` diagnostics |
| [Configuration](configuration.md) | All settings and environment variables |

## Architecture Overview

```
┌─────────────┐   ┌─────────────┐   ┌────────────┐
│  Web UI     │   │  Discord    │   │  Telegram  │
│  (Gradio)   │   │  Adapter    │   │  Adapter   │
└──────┬──────┘   └──────┬──────┘   └─────┬──────┘
       │                 │                │
       └────────┬────────┴────────┬───────┘
                │                 │
         ┌──────▼──────┐  ┌──────▼──────┐
         │   Agent     │  │  Tool       │
         │   (Core)    │  │  Registry   │
         └──────┬──────┘  └──────┬──────┘
                │                │
         ┌──────▼──────┐  ┌──────▼──────┐
         │  LLM Client │  │  Storage    │
         │  (Ollama)   │  │  (SQLite)   │
         └─────────────┘  └─────────────┘
```

### Key Components

- **Agent** (`core/agent.py`) — Orchestrates conversations, tool calls, and memory retrieval.
- **LLM Client** (`core/llm_client.py`) — Interfaces with Ollama's chat API, handles streaming and tool-call parsing.
- **Tool Registry** (`tools/`) — 20+ built-in tools (web search, files, code, calendar, etc.) and MCP server support.
- **Storage** (`storage/`) — SQLite-backed conversation history, memory, user settings, and credential vault.
- **Platforms** (`platforms/`) — Adapters for Discord, Telegram, and the Gradio web UI.
- **Scheduler** (`core/scheduler.py`) — Cron-like task scheduler for recurring actions.
- **UI** (`ui/app.py`) — Full-featured Gradio web interface with theme support, settings panels, and tool management.

## CLI Reference

Local Pigeon ships a `botf` CLI (via [Typer](https://typer.tiangolo.com)):

```bash
botf run              # Launch the web UI (default)
botf run --discord    # Launch the Discord bot
botf run --telegram   # Launch the Telegram bot
botf chat             # Interactive terminal chat
botf doctor           # Run diagnostic health checks
botf status           # Show connection and model status
botf models           # List / pull Ollama models
botf setup            # Interactive first-run wizard
botf logs             # View recent log output
botf eval             # Run tool-usage evaluations
botf version          # Print version
```

## Privacy Guarantee

All data stays on your machine:

- LLM inference runs locally via Ollama — no API calls to cloud providers.
- Conversations and memories are stored in a local SQLite database.
- Credentials are encrypted at rest in `~/.local_pigeon/credentials/`.
- No telemetry, no analytics, no phoning home.
