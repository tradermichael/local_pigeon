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
    - macOS: ~/Library/Application Support/LocalPigeon
    - Linux: ~/.local/share/local_pigeon (XDG compliant)
    
    Can be overridden via DATA_DIR or LOCAL_PIGEON_DATA environment variables.
    """
    # Check for explicit override
    data_dir = os.environ.get("LOCAL_PIGEON_DATA") or os.environ.get("DATA_DIR")
    if data_dir:
        path = Path(data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # Use system-appropriate location
    system = platform.system()
    
    if system == "Windows":
        # Windows: %LOCALAPPDATA%\LocalPigeon
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
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            path = Path(xdg_data) / "local_pigeon"
        else:
            path = Path.home() / ".local" / "share" / "local_pigeon"
    
    # Create directory if it doesn't exist
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    context_length: int = Field(default=8192, description="Context window size")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Generation temperature")
    max_tokens: int = Field(default=2048, description="Max tokens to generate")
    
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


class AgentSettings(BaseSettings):
    """Agent behavior settings."""
    
    system_prompt: str = Field(
        default="""You are Local Pigeon, a helpful AI assistant running locally on the user's device.
You have access to various tools including Google Workspace (Gmail, Calendar, Drive),
web search, and payment capabilities.

Always be helpful, concise, and respect user privacy.
When using tools, explain what you're doing before taking action.
For payments above the approval threshold, always request user confirmation.""",
        description="System prompt for the agent"
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
    
    # Storage and UI
    storage: StorageSettings = Field(default_factory=StorageSettings)
    ui: UISettings = Field(default_factory=UISettings)
    
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
    data_dir = get_data_dir()  # This creates the directory
    
    # Ensure .env file exists
    env_path = data_dir / ".env"
    if not env_path.exists():
        from datetime import datetime
        with open(env_path, "w") as f:
            f.write(f"# Local Pigeon Configuration\n")
            f.write(f"# Initialized: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Data directory: {data_dir}\n\n")
    
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
