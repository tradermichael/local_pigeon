# Configuration Reference

Local Pigeon uses [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for configuration. Values are read from environment variables, `.env` files, and `config.yaml`.

## Priority Order

1. **Environment variables** (highest priority)
2. **`.env` file** in the data directory (`~/.local_pigeon/.env`)
3. **`config.yaml`** in the project root
4. **Defaults** (lowest priority)

## Core Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OLLAMA_HOST` | `str` | `http://localhost:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `str` | `llama3.2` | Default model for conversations |
| `LP_DATA_DIR` | `str` | `~/.local_pigeon` | Base directory for all data |
| `LP_LOG_LEVEL` | `str` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `LP_PORT` | `int` | `7860` | Web UI listen port |
| `LP_HOST` | `str` | `0.0.0.0` | Web UI bind address |

## Platform Tokens

| Variable | Description |
|----------|-------------|
| `DISCORD_BOT_TOKEN` | Discord bot token from Developer Portal |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |

## Tool API Keys

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Google API key (Search, YouTube, etc.) |
| `GOOGLE_CX_ID` | Google Custom Search engine ID |
| `BRAVE_API_KEY` | Brave Search API key |
| `OPENWEATHERMAP_API_KEY` | OpenWeatherMap API key |

## Model Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OLLAMA_TEMPERATURE` | `float` | `0.7` | Sampling temperature |
| `OLLAMA_NUM_CTX` | `int` | `32768` | Context window size |
| `OLLAMA_TOP_P` | `float` | `0.9` | Top-p sampling |
| `OLLAMA_TOP_K` | `int` | `40` | Top-k sampling |

## MCP Servers

MCP (Model Context Protocol) servers are configured in `config.yaml`:

```yaml
mcp_servers:
  - name: my-tools
    url: http://localhost:8080
    enabled: true
```

## Data Directory Layout

```
~/.local_pigeon/
├── .env                # Environment overrides
├── pigeon.db           # SQLite database (conversations, memory)
├── credentials/        # Encrypted credential store
├── logs/               # Application logs
│   └── pigeon.log
└── sessions/           # Session data
```
