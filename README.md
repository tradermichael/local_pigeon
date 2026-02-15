# 🕊️ Local Pigeon

```
  _                     _   ____  _                       
 | |    ___   ___ __ _| | |  _ \(_) __ _  ___  ___  _ __  
 | |   / _ \ / __/ _` | | | |_) | |/ _` |/ _ \/ _ \| '_ \ 
 | |__| (_) | (_| (_| | | |  __/| | (_| |  __/ (_) | | | |
 |_____\___/ \___\__,_|_| |_|   |_|\__, |\___|\___/|_| |_|
                                   |___/                  
```

**A fully local AI agent powered by Ollama (or llama-cpp-python).** Your AI assistant that runs entirely on your device, connecting to Discord, Telegram, or a web interface while keeping all LLM inference local and private.

[![PyPI version](https://img.shields.io/pypi/v/local-pigeon.svg)](https://pypi.org/project/local-pigeon/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- 🧠 **Local LLM Inference** - Uses Ollama for on-device model inference
- 🔐 **Privacy First** - Your conversations never leave your device
- 💬 **Multi-Platform** - Discord, Telegram, and Web UI support
- 🔧 **Extensible Tools** - Web search, browser automation, and more
- 🌐 **Browser Automation** - Navigate dynamic websites (Google Flights, etc.)
- 🎤 **Voice Input** - Speech-to-text for hands-free interaction
- 📧 **Google Workspace** - Gmail, Calendar, and Drive integration
- 💳 **Payment Capabilities** - Stripe virtual cards and crypto (USDC/ETH)
- ✅ **Human-in-the-Loop** - Approval workflow for sensitive operations
- 📊 **Activity Dashboard** - Track interactions across all platforms
- 🚀 **Easy Setup** - One-command installation

## 📋 Prerequisites

- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **Ollama** ([Download](https://ollama.ai)) - *or Local Pigeon can auto-download models via llama-cpp-python*
- A supported LLM model (e.g., `gemma3`, `llama3.2`, `qwen2.5`)

## 🚀 Quick Start

### Option 1: Auto-Installer (Recommended)

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/tradermichael/local_pigeon/main/install.ps1 | iex
```

**Mac/Linux:**
```bash
curl -sSL https://raw.githubusercontent.com/tradermichael/local_pigeon/main/install.sh | bash
```

### Option 2: pip Install

```bash
pip install local-pigeon

# Optional features:
pip install local-pigeon[browser]  # Browser automation (Playwright)
pip install local-pigeon[voice]    # Voice input (Speech Recognition)
pip install local-pigeon[all]      # Everything
```

### Option 3: From Source

```bash
git clone https://github.com/tradermichael/local_pigeon.git
cd local_pigeon
pip install -e .
```

### Option 4: Docker

```bash
docker-compose up -d
```

## ⚙️ Configuration

### 1. Set up Ollama (or skip for auto-download)

If you have Ollama installed, make sure it's running:

```bash
# Start Ollama (if not running)
ollama serve

# Pull a model
ollama pull gemma3:latest
```

**No Ollama?** Local Pigeon will automatically fall back to llama-cpp-python and download a model from HuggingFace on first run.

### 2. Configure Local Pigeon

Run the setup wizard:

```bash
local-pigeon setup
```

Or manually create a `.env` file:

```env
# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma3:latest

# Discord (optional)
DISCORD_BOT_TOKEN=your_discord_bot_token

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Google Workspace (optional)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# Browser automation (optional)
BROWSER_ENABLED=true
BROWSER_HEADLESS=true  # false to see browser window

# Payments (optional)
STRIPE_API_KEY=sk_...
PAYMENT_APPROVAL_THRESHOLD=25.00
```

### 3. Run Local Pigeon

```bash
# Start all enabled platforms
local-pigeon run

# Or run specific platform
local-pigeon run --platform discord
local-pigeon run --platform telegram
local-pigeon run --platform web
```

## 💬 Platforms

### Discord Bot

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable "Message Content Intent" under Bot settings
3. Copy the bot token to your `.env`
4. Invite the bot to your server with appropriate permissions

**Features:**
- Responds to mentions and DMs
- Streaming responses with message edits
- Slash commands: `/model`, `/clear`, `/status`
- Payment approval via DM

### Telegram Bot

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Copy the bot token to your `.env`
3. Optionally set `TELEGRAM_ALLOWED_USERS` to restrict access

**Features:**
- Message handling with user whitelist
- Streaming responses
- Commands: `/model`, `/clear`, `/status`
- Inline keyboard for payment approvals

### Web UI

Access at `http://localhost:7860` when running with `--platform web`.

**Features:**
- Chat interface with streaming
- Voice input (microphone)
- Activity log across all platforms
- Settings panel
- OAuth setup for Google
- Tool execution display

## 🧰 Tools

### Web Tools
- **Web Search** - Search using DuckDuckGo
- **Web Fetch** - Extract content from web pages
- **Browser** - Full browser automation (Playwright)
- **Browser Search** - Specialized search tasks (Google Flights, etc.)

### Google Workspace
- **Gmail** - Read, search, and send emails
- **Calendar** - View and create events
- **Drive** - List, search, and read files

### Payments
- **Stripe Card** - Virtual card for online payments
- **Crypto Wallet** - USDC/ETH on Base network

### Discord Tools
- **Send Messages** - Post to channels
- **Send DMs** - Direct message users
- **Get Messages** - Read channel history
- **Add Reactions** - React to messages
- **List Channels** - See available channels
- **Create Threads** - Start discussion threads

## 💳 Payment System

Local Pigeon supports both traditional and crypto payments:

### Stripe Virtual Cards
- Create virtual cards for online purchases
- Real-time transaction monitoring
- Human-in-the-loop approval for amounts above threshold

### Crypto Wallet (CDP)
- USDC and ETH support on Base network
- Send and receive payments
- Approval workflow for security

### Approval Workflow

Payments above your configured threshold (default: $25) require approval:

1. Agent requests payment
2. You receive approval request (Discord DM, Telegram message, or Web UI)
3. Approve or deny within 5 minutes
4. Payment proceeds or is cancelled

Configure threshold:
```env
PAYMENT_APPROVAL_THRESHOLD=25.00
```

## 🔐 Security

- **Local Processing** - LLM runs on your device via Ollama
- **Encrypted Storage** - OAuth tokens encrypted at rest
- **Human Approval** - Sensitive operations require confirmation
- **User Whitelist** - Restrict bot access to specific users

## 📁 Project Structure

```
local_pigeon/
├── src/
│   └── local_pigeon/
│       ├── core/           # Agent, LLM client, conversation
│       ├── platforms/      # Discord, Telegram adapters
│       ├── tools/          # Web, Google, Payment, Discord tools
│       │   ├── web/        # Search, fetch, browser automation
│       │   ├── google/     # Gmail, Calendar, Drive
│       │   ├── discord/    # Discord action tools
│       │   └── payments/   # Stripe, crypto wallet
│       ├── storage/        # Database, credentials
│       ├── ui/             # Gradio web interface
│       ├── config.py       # Configuration management
│       └── cli.py          # Command-line interface
├── config.yaml             # YAML configuration
├── .env.example            # Environment template
├── install.ps1             # Windows installer
├── install.sh              # Mac/Linux installer
├── Dockerfile              # Docker build
└── docker-compose.yml      # Docker orchestration
```

## 🛠️ Development

### Setup Development Environment

```bash
git clone https://github.com/tradermichael/local_pigeon.git
cd local_pigeon
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Code Style

```bash
ruff check .
ruff format .
```

## 📝 Commands Reference

```bash
# Run the agent
local-pigeon run [--platform discord|telegram|web]

# Interactive setup wizard
local-pigeon setup

# Check system status
local-pigeon status

# List available models
local-pigeon models

# Interactive chat (terminal)
local-pigeon chat

# Show version
local-pigeon version
```

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai) - Local LLM runtime
- [Playwright](https://playwright.dev) - Browser automation
- [discord.py](https://discordpy.readthedocs.io/) - Discord API wrapper
- [aiogram](https://docs.aiogram.dev/) - Telegram Bot framework
- [Gradio](https://gradio.app) - Web UI framework
- [Stripe](https://stripe.com) - Payment processing
- [Coinbase CDP](https://docs.cdp.coinbase.com/) - Crypto infrastructure

---

**Made with ❤️ for local-first AI**
