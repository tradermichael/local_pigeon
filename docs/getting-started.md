# Getting Started

## Prerequisites

- **Python 3.10+** — Local Pigeon requires Python 3.10 or higher.
- **Ollama** — Install from [ollama.com](https://ollama.com). This provides the local LLM backend.

## Installation

### From PyPI (recommended)

```bash
pip install local-pigeon
```

### From source

```bash
git clone https://github.com/tradermichael/local_pigeon.git
cd local_pigeon
pip install -e ".[dev]"
```

### Docker

```bash
docker compose up -d
```

See the project [docker-compose.yml](../docker-compose.yml) for the full service definition.

## First Launch

### 1. Start Ollama

Make sure the Ollama daemon is running:

```bash
ollama serve
```

### 2. Pull a model

```bash
ollama pull llama3.2
```

Or let Local Pigeon pull it automatically on first run.

### 3. Run the setup wizard

```bash
botf setup
```

This walks you through selecting a model, configuring optional services (Discord, Telegram, web search), and setting data directories.

### 4. Launch

```bash
botf run
```

The web UI opens at [http://localhost:7860](http://localhost:7860) by default.

## Platform Setup

### Discord

1. Create a bot at [discord.com/developers](https://discord.com/developers/applications).
2. Copy the bot token.
3. Run `botf setup` and enter the token when prompted, or set `DISCORD_BOT_TOKEN` in your `.env`.
4. Launch with `botf run --discord`.

### Telegram

1. Talk to [@BotFather](https://t.me/BotFather) on Telegram and create a new bot.
2. Copy the token.
3. Run `botf setup` and enter the token, or set `TELEGRAM_BOT_TOKEN` in your `.env`.
4. Launch with `botf run --telegram`.

## Configuration

Local Pigeon reads settings from (in priority order):

1. **Environment variables** — e.g. `OLLAMA_HOST`, `DISCORD_BOT_TOKEN`
2. **`.env` file** — in `~/.local_pigeon/.env`
3. **`config.yaml`** — project-level defaults

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.2` | Default model for chat |
| `LP_DATA_DIR` | `~/.local_pigeon` | Data directory for DB, logs, creds |
| `LP_LOG_LEVEL` | `INFO` | Logging verbosity |
| `LP_PORT` | `7860` | Web UI port |

For the full list, see [Configuration](configuration.md).

## Verify Installation

Run the built-in diagnostics to confirm everything is working:

```bash
botf doctor
```

This checks Python version, Ollama connectivity, model availability, database integrity, and platform credentials. See [Troubleshooting](troubleshooting.md) for common fixes.
