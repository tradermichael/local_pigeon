"""
Local Pigeon Configuration Management

Handles loading configuration from environment variables, .env files,
and config.yaml with proper validation using Pydantic.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import platform


def get_data_dir() -> Path:
    """
    Get the data directory for Local Pigeon.
    
    Uses proper system-level locations:
    - Windows: %LOCALAPPDATA%\\LocalPigeon
    - Windows Store Python: %LOCALAPPDATA%\\Packages\\<package>\\LocalCache\\Local\\LocalPigeon
    - macOS: ~/Library/Application Support/LocalPigeon
    - Linux: ~/.local/share/local_pigeon (XDG compliant)
    
    Can be overridden via DATA_DIR or LOCAL_PIGEON_DATA environment variables.
    
    Automatically detects virtualized environments (Windows Store, Snap, Flatpak)
    and returns the correct physical path where files actually exist.
    """
    import sys
    
    # Check for explicit override
    data_dir = os.environ.get("LOCAL_PIGEON_DATA") or os.environ.get("DATA_DIR")
    if data_dir:
        path = Path(data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # Use system-appropriate location
    system = platform.system()
    
    if system == "Windows":
        # Prefer Windows Store Python LocalCache if present (some store builds don't include WindowsApps in sys.executable)
        try:
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            packages_dir = Path(local_app_data) / "Packages"
            if packages_dir.exists():
                matches = sorted(packages_dir.glob("PythonSoftwareFoundation.Python.*"))
                for match in matches:
                    candidate = match / "LocalCache" / "Local" / "LocalPigeon"
                    # If it already exists or we can create it, use it
                    candidate.mkdir(parents=True, exist_ok=True)
                    return candidate
        except Exception:
            pass

        # Check if using Windows Store Python (virtualized filesystem)
        if "WindowsApps" in sys.executable:
            # Extract the package name from the executable path
            # e.g., PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0
            try:
                exe_parts = Path(sys.executable).parts
                for part in exe_parts:
                    if part.startswith("PythonSoftwareFoundation.Python"):
                        # Build the actual path in LocalCache
                        local_app_data = os.environ.get("LOCALAPPDATA", "")
                        path = Path(local_app_data) / "Packages" / part / "LocalCache" / "Local" / "LocalPigeon"
                        path.mkdir(parents=True, exist_ok=True)
                        return path
            except Exception:
                pass
        
        # Regular Windows: %LOCALAPPDATA%\LocalPigeon
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            path = Path(local_app_data) / "LocalPigeon"
        else:
            path = Path.home() / "AppData" / "Local" / "LocalPigeon"
    
    elif system == "Darwin":
        # macOS: ~/Library/Application Support/LocalPigeon
        path = Path.home() / "Library" / "Application Support" / "LocalPigeon"
    
    else:
        # Linux/Unix: ~/.local/share/local_pigeon (XDG Base Directory)
        # Check for Snap package
        snap_data = os.environ.get("SNAP_USER_DATA")
        if snap_data:
            path = Path(snap_data) / "LocalPigeon"
            path.mkdir(parents=True, exist_ok=True)
            return path
        
        # Check for Flatpak
        if os.environ.get("FLATPAK_ID"):
            flatpak_data = os.environ.get("XDG_DATA_HOME")
            if flatpak_data:
                path = Path(flatpak_data) / "local_pigeon"
                path.mkdir(parents=True, exist_ok=True)
                return path
        
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            path = Path(xdg_data) / "local_pigeon"
        else:
            path = Path.home() / ".local" / "share" / "local_pigeon"
    
    # Create directory if it doesn't exist
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_python_environment_info() -> dict[str, str]:
    """
    Detect the Python environment type and return relevant information.
    
    Returns:
        Dict with keys: 'type', 'version', 'executable', 'virtualized'
    """
    import sys
    
    exe = sys.executable
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    env_type = "system"
    virtualized = False
    
    if platform.system() == "Windows":
        if "WindowsApps" in exe:
            env_type = "windows_store"
            virtualized = True
        elif "anaconda" in exe.lower() or "conda" in exe.lower():
            env_type = "conda"
        elif "envs" in exe.lower() or "venv" in exe.lower() or ".venv" in exe.lower():
            env_type = "virtualenv"
        elif "pyenv" in exe.lower():
            env_type = "pyenv"
    elif platform.system() == "Darwin":
        if "/usr/local/Cellar" in exe or "homebrew" in exe.lower():
            env_type = "homebrew"
        elif "anaconda" in exe.lower() or "conda" in exe.lower():
            env_type = "conda"
        elif "pyenv" in exe.lower():
            env_type = "pyenv"
        elif "envs" in exe.lower() or "venv" in exe.lower():
            env_type = "virtualenv"
    else:  # Linux
        if "anaconda" in exe.lower() or "conda" in exe.lower():
            env_type = "conda"
        elif "pyenv" in exe.lower():
            env_type = "pyenv"
        elif "envs" in exe.lower() or "venv" in exe.lower():
            env_type = "virtualenv"
    
    return {
        "type": env_type,
        "version": version,
        "executable": exe,
        "virtualized": str(virtualized),
    }


def get_physical_data_dir() -> Path:
    """
    Get the actual physical path to the data directory.
    
    This resolves filesystem virtualization/sandboxing:
    - Windows Store Python: Files are stored in package's LocalCache folder
    - Snap/Flatpak on Linux: May have similar sandboxing
    - Regular Python: Returns the same as get_data_dir()
    
    The function auto-detects the Python environment and returns the correct
    physical path where files actually exist on disk.
    
    Returns:
        The physical path where data files actually exist on disk.
    """
    import sys
    
    logical_path = get_data_dir()
    
    # Check if using Windows Store Python (virtualized filesystem)
    if platform.system() == "Windows" and "WindowsApps" in sys.executable:
        # Extract the package name from the executable path
        # e.g., PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0
        try:
            exe_parts = Path(sys.executable).parts
            for part in exe_parts:
                if part.startswith("PythonSoftwareFoundation.Python"):
                    # Build the actual path in LocalCache
                    local_app_data = os.environ.get("LOCALAPPDATA", "")
                    physical_path = Path(local_app_data) / "Packages" / part / "LocalCache" / "Local" / "LocalPigeon"
                    # Return this path even if it doesn't exist yet (it will be created)
                    physical_path.mkdir(parents=True, exist_ok=True)
                    return physical_path
        except Exception:
            pass
    
    # Linux Snap package detection
    if platform.system() == "Linux" and os.environ.get("SNAP"):
        # Snap apps have $SNAP_USER_DATA for persistent storage
        snap_data = os.environ.get("SNAP_USER_DATA")
        if snap_data:
            physical_path = Path(snap_data) / "LocalPigeon"
            physical_path.mkdir(parents=True, exist_ok=True)
            return physical_path
    
    # Linux Flatpak detection
    if platform.system() == "Linux" and os.environ.get("FLATPAK_ID"):
        # Flatpak uses XDG directories but may be sandboxed
        flatpak_data = os.environ.get("XDG_DATA_HOME")
        if flatpak_data:
            physical_path = Path(flatpak_data) / "local_pigeon"
            physical_path.mkdir(parents=True, exist_ok=True)
            return physical_path
    
    return logical_path


def get_models_dir() -> Path:
    """
    Get the directory for storing downloaded models.
    
    Returns:
        Path to models directory
    """
    models_dir = get_data_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def load_yaml_config() -> dict[str, Any]:
    """Load configuration from config.yaml if it exists."""
    data_dir = get_data_dir()
    config_path = data_dir / "config.yaml"
    
    if not config_path.exists():
        # Try current directory
        config_path = Path("config.yaml")
    
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    
    return {}


class OllamaSettings(BaseSettings):
    """Ollama LLM settings."""
    
    host: str = Field(default="http://localhost:11434", description="Ollama API host")
    model: str = Field(default="gemma3:latest", description="Default model to use")
    vision_model: str = Field(default="", description="Vision model for image processing (auto-detected if empty)")
    fallback_models: list[str] = Field(
        default_factory=lambda: ["llama3.1:8b", "qwen2.5:7b", "mistral:7b"],
        description="Fallback models to try if primary model returns empty"
    )
    context_length: int = Field(default=8192, description="Context window size")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Generation temperature")
    max_tokens: int = Field(default=2048, description="Max tokens to generate")
    max_retries: int = Field(default=3, description="Max retries for empty responses before fallback")
    retry_delay: float = Field(default=0.5, description="Delay between retries in seconds")
    
    model_config = SettingsConfigDict(env_prefix="OLLAMA_")


class DiscordSettings(BaseSettings):
    """Discord bot settings."""
    
    bot_token: str = Field(default="", description="Discord bot token")
    app_id: str = Field(default="", description="Discord application ID (for invite URL)")
    allowed_channels: list[str] = Field(default_factory=list, description="Allowed channel IDs")
    admin_users: list[str] = Field(default_factory=list, description="Admin user IDs")
    enabled: bool = Field(default=False, description="Enable Discord bot")
    mention_only: bool = Field(default=True, description="Only respond to mentions")
    show_typing: bool = Field(default=True, description="Show typing indicator")
    max_message_length: int = Field(default=2000, description="Max message length")
    
    model_config = SettingsConfigDict(env_prefix="DISCORD_")
    
    @field_validator("allowed_channels", "admin_users", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v or []


class TelegramSettings(BaseSettings):
    """Telegram bot settings."""
    
    bot_token: str = Field(default="", description="Telegram bot token")
    allowed_users: list[str] = Field(default_factory=list, description="Allowed user IDs")
    enabled: bool = Field(default=False, description="Enable Telegram bot")
    show_typing: bool = Field(default=True, description="Show typing indicator")
    parse_mode: str = Field(default="HTML", description="Message parse mode")
    
    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")
    
    @field_validator("allowed_users", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v or []


class GoogleSettings(BaseSettings):
    """Google Workspace settings."""
    
    credentials_path: str = Field(default="credentials.json", description="OAuth credentials file")
    gmail_enabled: bool = Field(default=False, description="Enable Gmail integration")
    calendar_enabled: bool = Field(default=False, description="Enable Calendar integration")
    drive_enabled: bool = Field(default=False, description="Enable Drive integration")
    calendar_id: str = Field(default="primary", description="Default calendar ID")
    
    model_config = SettingsConfigDict(env_prefix="GOOGLE_")


class PaymentApprovalSettings(BaseSettings):
    """Payment approval settings."""
    
    threshold: float = Field(default=25.0, ge=0, description="Approval threshold (USD)")
    daily_limit: float = Field(default=100.0, ge=0, description="Daily spending limit (USD)")
    timeout: int = Field(default=300, ge=30, description="Approval timeout (seconds)")
    require_approval: bool = Field(default=True, description="Require approval for all payments")


class StripeSettings(BaseSettings):
    """Stripe payment settings."""
    
    api_key: str = Field(default="", description="Stripe API key")
    webhook_secret: str = Field(default="", description="Stripe webhook secret")
    enabled: bool = Field(default=False, description="Enable Stripe payments")
    spending_limit_per_transaction: float = Field(default=50.0, description="Per-transaction limit")
    
    model_config = SettingsConfigDict(env_prefix="STRIPE_")


class CryptoSettings(BaseSettings):
    """Cryptocurrency wallet settings."""
    
    cdp_api_key_name: str = Field(default="", description="Coinbase CDP API key name")
    cdp_api_key_private_key: str = Field(default="", description="Coinbase CDP private key")
    enabled: bool = Field(default=False, description="Enable crypto wallet")
    network: str = Field(default="base", description="Default network")
    
    model_config = SettingsConfigDict(env_prefix="CDP_")


class PaymentSettings(BaseSettings):
    """Combined payment settings."""
    
    stripe: StripeSettings = Field(default_factory=StripeSettings)
    crypto: CryptoSettings = Field(default_factory=CryptoSettings)
    approval: PaymentApprovalSettings = Field(default_factory=PaymentApprovalSettings)


class WebSearchSettings(BaseSettings):
    """Web search settings."""
    
    enabled: bool = Field(default=True, description="Enable web search")
    provider: str = Field(default="duckduckgo", description="Search provider")
    searxng_url: str = Field(default="", description="SearXNG instance URL")
    max_results: int = Field(default=5, ge=1, le=20, description="Max search results")
    safe_search: str = Field(default="moderate", description="Safe search level")


class WebFetchSettings(BaseSettings):
    """Web page fetch settings."""
    
    enabled: bool = Field(default=True, description="Enable page fetching")
    max_content_length: int = Field(default=10000, description="Max content length")
    timeout: int = Field(default=30, description="Request timeout")
    user_agent: str = Field(default="LocalPigeon/0.1", description="User agent string")


class BrowserSettings(BaseSettings):
    """Browser automation settings (Playwright)."""
    
    enabled: bool = Field(default=False, description="Enable browser automation")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    timeout: int = Field(default=30000, description="Page navigation timeout (ms)")
    viewport_width: int = Field(default=1280, description="Browser viewport width")
    viewport_height: int = Field(default=720, description="Browser viewport height")
    
    model_config = SettingsConfigDict(env_prefix="BROWSER_")


class MCPServerSettings(BaseSettings):
    """Settings for a single MCP server."""
    
    name: str = Field(default="", description="Unique name for this MCP server")
    transport: str = Field(default="stdio", description="Transport type: stdio or sse")
    command: str = Field(default="npx", description="Command to launch stdio server")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    url: str = Field(default="", description="URL for SSE transport server")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    
    model_config = SettingsConfigDict(extra="allow")


class MCPSettings(BaseSettings):
    """MCP (Model Context Protocol) settings."""
    
    enabled: bool = Field(default=False, description="Enable MCP tool integration")
    servers: list[MCPServerSettings] = Field(
        default_factory=list,
        description="List of MCP servers to connect to"
    )
    auto_approve: bool = Field(
        default=False,
        description="Auto-approve MCP tool calls (vs requiring approval)"
    )
    connection_timeout: int = Field(
        default=30,
        description="Timeout for connecting to MCP servers (seconds)"
    )
    
    model_config = SettingsConfigDict(env_prefix="MCP_")


class WebSettings(BaseSettings):
    """Combined web settings."""
    
    search: WebSearchSettings = Field(default_factory=WebSearchSettings)
    fetch: WebFetchSettings = Field(default_factory=WebFetchSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)


class StorageSettings(BaseSettings):
    """Storage settings."""
    
    database: str = Field(default="local_pigeon.db", description="Database filename")
    history_retention_days: int = Field(default=90, ge=0, description="History retention (0=forever)")
    encrypt_credentials: bool = Field(default=True, description="Encrypt stored credentials")


class UISettings(BaseSettings):
    """Web UI settings."""
    
    host: str = Field(default="127.0.0.1", description="UI host")
    port: int = Field(default=7860, description="UI port")
    share: bool = Field(default=False, description="Create public Gradio link")
    theme: str = Field(default="soft", description="UI theme")
    show_tool_details: bool = Field(default=True, description="Show tool execution details")
    show_history: bool = Field(default=True, description="Show chat history")
    
    model_config = SettingsConfigDict(env_prefix="WEBUI_")


class MeshSettings(BaseSettings):
    """Optional mesh/federation networking settings."""

    enabled: bool = Field(default=False, description="Enable mesh networking")
    public_key: str = Field(default="", description="WireGuard public key")
    private_key: str = Field(default="", description="WireGuard private key")

    model_config = SettingsConfigDict(env_prefix="MESH_")


class AgentSettings(BaseSettings):
    """Agent behavior settings."""
    
    default_bot_name: str = Field(
        default="Pigeon",
        description="Default name for the bot (can be overridden per-user)"
    )
    
    system_prompt: str = Field(
        default="""You are {bot_name}, a helpful AI assistant running locally on the user's device.

CRITICAL INSTRUCTION - TOOL USAGE:
You have tools available. When the user asks for something a tool can do, YOU MUST CALL THE TOOL.

DO NOT:
- Say "I can't access your email" - you CAN, use the gmail tool
- Say "I don't have real-time information" - you DO, use web_search
- Explain how to do things manually - just DO IT with the tool
- Refuse due to privacy concerns - the user authorized these tools

DO:
- Call gmail tool when user asks about emails
- Call calendar tool when user asks about events/schedule
- Call web_search when user needs current information
- Call drive tool when user asks about their files

USER-AUTHORIZED SERVICES (gmail, calendar, drive):
The user has already connected and authorized these accounts via OAuth.
You have full permission to read, search, and interact with THEIR OWN data.
This is NOT someone else's data - it's the user's own authorized accounts.

When the user says "check my email" or "what's on my calendar", immediately call the tool.
Do not ask for permission, do not explain privacy concerns - just use the tool.

FACTUAL GROUNDING (CRITICAL):
For questions about facts, current events, people (president, CEO, leader), statistics, or anything that could change:
- ALWAYS use web_search BEFORE answering - DO NOT answer from memory
- Never guess at facts, dates, names, or current positions
- Your training data is OUTDATED - it does not know recent events
- Examples: "who is the president", "who won the Super Bowl", "what's Bitcoin price"

WHEN USING SEARCH RESULTS - THIS IS MANDATORY:
- The search results are CURRENT and CORRECT. Your training data is OLD and WRONG.
- If search results say X and your training says Y, the search results are RIGHT.
- NEVER say "search results appear outdated" - YOUR TRAINING is outdated, not the search.
- Report EXACTLY what the search results say, even if it surprises you.
- Example: If search says "Donald Trump is president" but you think it's Biden, TRUST THE SEARCH.
- Do NOT mix search results with your training data - use ONLY what the search returned.
- CITE YOUR SOURCES: Include "According to [source name]" when stating facts from search results.

ANTI-HALLUCINATION - CRITICAL:
- NEVER invent restaurant names, business names, addresses, phone numbers, ratings, or prices.
- If search snippets don't contain the specific detail, say "I found some results but don't have the exact [detail]" instead of making something up.
- For recommendations (restaurants, shops, places): use web_fetch on the top search result URLs to get actual names, ratings, and details BEFORE answering.
- Only mention businesses/places that appear VERBATIM in search results or fetched page content.
- If you cannot verify a name or address from tool output, DO NOT include it in your response.

COMPLETING TASKS:
After you call a tool and get results, PROVIDE YOUR FINAL ANSWER to the user.
Do NOT call the same tool again unless you need different data.
One tool call is usually enough - list files once, search once, then answer.
If you have the information needed, STOP using tools and respond directly.

MULTI-PART REQUESTS (CRITICAL):
If the user asks for MULTIPLE things (e.g., "who is the president AND check my email"):
- You MUST call ALL relevant tools - do NOT hallucinate results
- NEVER pretend to check something without calling the actual tool
- Example: "who is the president and check my email" requires BOTH web_search AND gmail
- If the user mentions email/inbox: you MUST call gmail tool
- If the user mentions calendar/schedule: you MUST call calendar tool
- If the user mentions facts/current events: you MUST call web_search
- NEVER say "your inbox doesn't contain X" without actually calling gmail first
- Each tool provides DIFFERENT information - use ALL that are relevant""",
        description="System prompt for the agent (use {bot_name} and {user_name} as placeholders)"
    )
    max_history_messages: int = Field(default=20, ge=1, description="Max history messages")
    tools_enabled: bool = Field(default=True, description="Enable tool usage")
    checkpoint_mode: bool = Field(
        default=False,
        description="Ralph Loop: Require approval for each tool execution (human-in-the-loop)"
    )
    max_tool_iterations: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum tool execution iterations per request"
    )
    
    # Heartbeat / Self-improvement settings
    heartbeat_enabled: bool = Field(
        default=False,
        description="Enable periodic self-reflection for skill learning"
    )
    heartbeat_interval_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Minutes between heartbeat reflections"
    )
    auto_approve_skills: bool = Field(
        default=False,
        description="Auto-approve skills proposed by the agent (vs requiring user approval)"
    )


class Settings(BaseSettings):
    """Main settings container for Local Pigeon."""
    
    # Core settings
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    
    # Platform settings
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    
    # Tool settings
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    payments: PaymentSettings = Field(default_factory=PaymentSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    
    # Storage and UI
    storage: StorageSettings = Field(default_factory=StorageSettings)
    ui: UISettings = Field(default_factory=UISettings)
    mesh: MeshSettings = Field(default_factory=MeshSettings)
    
    # Security
    encryption_key: str = Field(default="", description="Encryption key for credentials")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment and config files."""
        # Load .env from data directory first
        data_dir = get_data_dir()
        env_path = data_dir / ".env"
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path, override=True)
        
        # Load YAML config
        yaml_config = load_yaml_config()
        
        # Create settings (env vars override YAML)
        settings = cls()
        
        # Apply YAML config for nested settings that aren't easily set via env
        # BUT only if the env var wasn't explicitly set
        if "model" in yaml_config:
            model_config = yaml_config["model"]
            # Only use YAML value if env var not set (pydantic default still in place)
            if "name" in model_config and not os.environ.get("OLLAMA_MODEL"):
                settings.ollama.model = model_config["name"]
            if "context_length" in model_config and not os.environ.get("OLLAMA_CONTEXT_LENGTH"):
                settings.ollama.context_length = model_config["context_length"]
            if "temperature" in model_config and not os.environ.get("OLLAMA_TEMPERATURE"):
                settings.ollama.temperature = model_config["temperature"]
        
        if "agent" in yaml_config:
            agent_config = yaml_config["agent"]
            if "system_prompt" in agent_config:
                settings.agent.system_prompt = agent_config["system_prompt"]
            if "max_history_messages" in agent_config:
                settings.agent.max_history_messages = agent_config["max_history_messages"]
            if "tools_enabled" in agent_config:
                settings.agent.tools_enabled = agent_config["tools_enabled"]
        
        if "platforms" in yaml_config:
            platforms = yaml_config["platforms"]
            if "discord" in platforms:
                discord_config = platforms["discord"]
                for key, value in discord_config.items():
                    if hasattr(settings.discord, key):
                        setattr(settings.discord, key, value)
            if "telegram" in platforms:
                telegram_config = platforms["telegram"]
                for key, value in telegram_config.items():
                    if hasattr(settings.telegram, key):
                        setattr(settings.telegram, key, value)
        
        # Handle Google section (env vars take priority over YAML)
        if "google" in yaml_config:
            google_config = yaml_config["google"]
            # Gmail settings
            if "gmail" in google_config:
                gmail_config = google_config["gmail"]
                if "enabled" in gmail_config and not os.environ.get("GOOGLE_GMAIL_ENABLED"):
                    settings.google.gmail_enabled = gmail_config["enabled"]
            # Calendar settings
            if "calendar" in google_config:
                cal_config = google_config["calendar"]
                if "enabled" in cal_config and not os.environ.get("GOOGLE_CALENDAR_ENABLED"):
                    settings.google.calendar_enabled = cal_config["enabled"]
                if "calendar_id" in cal_config and not os.environ.get("GOOGLE_CALENDAR_ID"):
                    settings.google.calendar_id = cal_config["calendar_id"]
            # Drive settings
            if "drive" in google_config:
                drive_config = google_config["drive"]
                if "enabled" in drive_config and not os.environ.get("GOOGLE_DRIVE_ENABLED"):
                    settings.google.drive_enabled = drive_config["enabled"]
        
        # Handle MCP section
        if "mcp" in yaml_config:
            mcp_config = yaml_config["mcp"]
            if "enabled" in mcp_config and not os.environ.get("MCP_ENABLED"):
                settings.mcp.enabled = mcp_config["enabled"]
            if "connection_timeout" in mcp_config:
                settings.mcp.connection_timeout = mcp_config["connection_timeout"]
            if "auto_approve" in mcp_config:
                settings.mcp.auto_approve = mcp_config["auto_approve"]
            if "servers" in mcp_config and mcp_config["servers"]:
                settings.mcp.servers = [
                    MCPServerSettings(**srv) for srv in mcp_config["servers"]
                ]
        
        # Apply env vars for nested settings (pydantic nested models don't auto-read env vars)
        # Discord
        if os.environ.get("DISCORD_ENABLED"):
            settings.discord.enabled = os.environ.get("DISCORD_ENABLED", "").lower() in ("true", "1", "yes")
        if os.environ.get("DISCORD_BOT_TOKEN"):
            settings.discord.bot_token = os.environ.get("DISCORD_BOT_TOKEN", "")
        if os.environ.get("DISCORD_APP_ID"):
            settings.discord.app_id = os.environ.get("DISCORD_APP_ID", "")
        if os.environ.get("DISCORD_MENTION_ONLY"):
            settings.discord.mention_only = os.environ.get("DISCORD_MENTION_ONLY", "").lower() in ("true", "1", "yes")
        
        # Telegram
        if os.environ.get("TELEGRAM_ENABLED"):
            settings.telegram.enabled = os.environ.get("TELEGRAM_ENABLED", "").lower() in ("true", "1", "yes")
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            settings.telegram.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        
        # Google
        if os.environ.get("GOOGLE_GMAIL_ENABLED"):
            settings.google.gmail_enabled = os.environ.get("GOOGLE_GMAIL_ENABLED", "").lower() in ("true", "1", "yes")
        if os.environ.get("GOOGLE_CALENDAR_ENABLED"):
            settings.google.calendar_enabled = os.environ.get("GOOGLE_CALENDAR_ENABLED", "").lower() in ("true", "1", "yes")
        if os.environ.get("GOOGLE_DRIVE_ENABLED"):
            settings.google.drive_enabled = os.environ.get("GOOGLE_DRIVE_ENABLED", "").lower() in ("true", "1", "yes")
        if os.environ.get("GOOGLE_CREDENTIALS_PATH"):
            settings.google.credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
        
        # Stripe
        if os.environ.get("STRIPE_ENABLED"):
            settings.payments.stripe.enabled = os.environ.get("STRIPE_ENABLED", "").lower() in ("true", "1", "yes")
        if os.environ.get("STRIPE_API_KEY"):
            settings.payments.stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
        
        # Ollama model
        if os.environ.get("OLLAMA_MODEL"):
            settings.ollama.model = os.environ.get("OLLAMA_MODEL", "")

        # Mesh
        if os.environ.get("MESH_ENABLED"):
            settings.mesh.enabled = os.environ.get("MESH_ENABLED", "").lower() in ("true", "1", "yes")
        if os.environ.get("MESH_PUBLIC_KEY"):
            settings.mesh.public_key = os.environ.get("MESH_PUBLIC_KEY", "")
        if os.environ.get("MESH_PRIVATE_KEY"):
            settings.mesh.private_key = os.environ.get("MESH_PRIVATE_KEY", "")
        
        return settings


# Global settings instance
_settings: Settings | None = None


def ensure_data_dir() -> Path:
    """
    Ensure the data directory exists and is properly initialized.
    
    Creates the directory structure and initializes .env file if missing.
    Call this early in application startup to ensure proper initialization.
    
    Returns:
        Path to the data directory
    """
    data_dir = get_data_dir()  # This creates the main directory
    
    # Create subdirectories
    subdirs = ["models", "logs", "backups", "skills", "skills/builtin", "skills/learned", "skills/custom"]
    for subdir in subdirs:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    # Ensure .env file exists with helpful template
    env_path = data_dir / ".env"
    if not env_path.exists():
        from datetime import datetime
        with open(env_path, "w") as f:
            f.write(f"# Local Pigeon Configuration\n")
            f.write(f"# Initialized: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Data directory: {data_dir}\n")
            f.write(f"#\n")
            f.write(f"# Settings are saved here automatically when you use the UI.\n")
            f.write(f"# You can also edit this file manually.\n")
            f.write(f"#\n")
            f.write(f"# Examples:\n")
            f.write(f"# OLLAMA_MODEL=deepseek-r1:7b\n")
            f.write(f"# DISCORD_ENABLED=true\n")
            f.write(f"# DISCORD_BOT_TOKEN=your_token_here\n")
            f.write(f"# GOOGLE_GMAIL_ENABLED=true\n")
            f.write(f"\n")
    
    return data_dir


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        # Ensure data directory exists before loading settings
        ensure_data_dir()
        _settings = Settings.load()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from disk."""
    global _settings
    ensure_data_dir()
    _settings = Settings.load()
    return _settings


def delete_local_data(keep_config: bool = True) -> dict[str, bool]:
    """
    Delete local data from the data directory.
    
    Args:
        keep_config: If True, preserve .env and config.yaml files
    
    Returns:
        dict with deleted items and status
    """
    import shutil
    
    data_dir = get_data_dir()
    results = {}
    
    # Files/directories to potentially delete
    items_to_delete = [
        "local_pigeon.db",  # Database (conversations, memories)
        "google_token.json",  # Google OAuth token
        "models",  # Downloaded models directory
    ]
    
    if not keep_config:
        items_to_delete.extend([".env", "config.yaml", "google_credentials.json"])
    
    for item in items_to_delete:
        item_path = data_dir / item
        try:
            if item_path.exists():
                if item_path.is_dir():
                    shutil.rmtree(item_path)
                else:
                    item_path.unlink()
                results[item] = True
            else:
                results[item] = False  # Didn't exist
        except Exception as e:
            results[item] = f"Error: {str(e)}"
    
    return results
