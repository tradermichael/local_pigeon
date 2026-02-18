# Troubleshooting

## `botf doctor`

The fastest way to diagnose issues is the built-in doctor command:

```bash
botf doctor
```

It checks:

| Check | What it verifies |
|-------|-----------------|
| Python version | ≥ 3.10 |
| Ollama running | API reachable at configured host |
| Models installed | At least one model pulled |
| Data directory | Exists and is writable |
| Database | SQLite file opens and has schema |
| Log directory | Exists and is writable |
| Google credentials | API key set (if using Google tools) |
| Discord config | Bot token configured |
| Telegram config | Bot token configured |
| MCP servers | Configured servers reachable |
| Optional deps | playwright, yt-dlp, etc. |

Each check reports ✅ pass, ⚠️ warning, or ❌ fail, with a suggested fix.

## Common Issues

### Ollama not reachable

**Symptom:** `botf doctor` shows ❌ for "Ollama running".

**Fix:**

```bash
# Start Ollama
ollama serve

# Or check if it's running on a non-default port
curl http://localhost:11434/api/tags
```

If Ollama is on a different host/port, set the environment variable:

```bash
export OLLAMA_HOST=http://your-host:11434
```

### No models found

**Symptom:** `botf doctor` shows ⚠️ for "Models installed".

**Fix:**

```bash
ollama pull llama3.2
# Or any model you prefer
ollama pull mistral
```

### Permission denied on data directory

**Symptom:** ❌ for "Data directory" with permission error.

**Fix:**

```bash
# Check ownership
ls -la ~/.local_pigeon

# Fix permissions
chmod 755 ~/.local_pigeon
```

Or set a custom data directory:

```bash
export LP_DATA_DIR=/path/to/your/data
```

### Discord bot not connecting

**Symptom:** Bot starts but doesn't respond to messages.

**Checklist:**

1. Verify the token: `botf doctor` should show ✅ for Discord.
2. Check bot permissions in the Discord Developer Portal — needs "Message Content Intent".
3. Ensure the bot is invited to your server with the correct OAuth2 scopes (`bot`, `applications.commands`).
4. Check logs: `botf logs`.

### Telegram bot not responding

**Symptom:** Bot appears online but ignores messages.

**Checklist:**

1. Verify token with `botf doctor`.
2. Make sure no other instance is polling the same bot token (Telegram only allows one poller).
3. Check logs: `botf logs`.

### Web UI won't start

**Symptom:** `botf run` fails or shows a blank page.

**Fix:**

```bash
# Check if port is in use
# Linux/macOS:
lsof -i :7860
# Windows:
netstat -ano | findstr 7860

# Use a different port
botf run --port 8080
```

### Database corruption

**Symptom:** Errors mentioning SQLite or "database is locked".

**Fix:**

```bash
# Back up the database
cp ~/.local_pigeon/pigeon.db ~/.local_pigeon/pigeon.db.bak

# Re-run to recreate
botf run
```

The agent will recreate missing tables on startup.

### MCP server connection failures

**Symptom:** `botf doctor` shows warnings for MCP servers.

**Fix:**

1. Verify the MCP server is running and accessible.
2. Check `config.yaml` for correct `mcp_servers` entries.
3. Test connectivity manually:

```bash
curl http://localhost:<mcp-port>/health
```

### Import errors after upgrade

**Symptom:** `ModuleNotFoundError` or `ImportError` after updating.

**Fix:**

```bash
pip install --upgrade local-pigeon
# Or from source:
pip install -e ".[dev]"
```

## Logs

View recent logs:

```bash
botf logs
```

Log files are stored in `~/.local_pigeon/logs/`. Set `LP_LOG_LEVEL=DEBUG` for verbose output.

## Getting Help

- **GitHub Issues:** [github.com/tradermichael/local_pigeon/issues](https://github.com/tradermichael/local_pigeon/issues)
- **Diagnostics:** Always include `botf doctor` output when filing an issue.
