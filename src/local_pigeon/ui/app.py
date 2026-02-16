"""
Gradio Web UI

Browser-based interface for Local Pigeon.
Provides:
- Chat interface with streaming
- Settings panel
- Integrations setup
- Memory management
- Tool execution display
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Generator
import gradio as gr

from local_pigeon import __version__
from local_pigeon.config import Settings, get_data_dir, ensure_data_dir, delete_local_data


def create_app(
    settings: Settings | None = None,
) -> gr.Blocks:
    """
    Create the Gradio web application.
    
    Args:
        settings: Application settings (loaded from config if not provided)
    
    Returns:
        Gradio Blocks application
    """
    if settings is None:
        settings = Settings.load()
    
    # Import here to avoid circular imports
    from local_pigeon.core.agent import LocalPigeonAgent
    from local_pigeon.storage.memory import AsyncMemoryManager, MemoryType
    
    # Create agent instance
    agent: LocalPigeonAgent | None = None
    memory_manager = AsyncMemoryManager(db_path=settings.storage.database)
    
    async def get_agent() -> LocalPigeonAgent:
        nonlocal agent
        if agent is None:
            agent = LocalPigeonAgent(settings)
            await agent.initialize()
        return agent
    
    with gr.Blocks(
        title="Local Pigeon",
    ) as app:
        # State
        conversation_state = gr.State([])
        
        # Header with logo and version
        gr.Markdown(
            f"""
# 🕊️ Local Pigeon

**v{__version__}** • Your local AI assistant powered by Ollama • 100% on-device
            """
        )
        
        with gr.Tabs():
            # Chat Tab
            with gr.Tab("💬 Chat"):
                chatbot = gr.Chatbot(
                    label="Conversation",
                    elem_classes="chatbot",
                    height=500,
                )
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        label="Message",
                        placeholder="Type your message here...",
                        lines=2,
                        scale=4,
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)
                
                with gr.Accordion("🎤 Voice Input", open=False):
                    with gr.Row():
                        voice_input = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            label="Click to record",
                            scale=2,
                        )
                        voice_status = gr.Textbox(
                            label="Transcription",
                            placeholder="Your speech will appear here...",
                            interactive=False,
                            scale=3,
                        )
                
                with gr.Row():
                    clear_btn = gr.Button("🗑️ Clear History")
                    model_dropdown = gr.Dropdown(
                        label="Model",
                        choices=[settings.ollama.model],
                        value=settings.ollama.model,
                        interactive=True,
                    )
                    refresh_models_btn = gr.Button("🔄 Refresh Models")
            
            # Memory Tab
            with gr.Tab("🧠 Memory"):
                gr.Markdown(
                    """
                    ### Your Memories
                    
                    Memories help Local Pigeon understand you better over time.
                    Add, edit, or remove information the agent knows about you.
                    """
                )
                
                with gr.Row():
                    with gr.Column(scale=2):
                        memories_display = gr.Dataframe(
                            headers=["Type", "Key", "Value", "Source"],
                            datatype=["str", "str", "str", "str"],
                            label="Stored Memories",
                            interactive=False,
                        )
                        refresh_memories_btn = gr.Button("🔄 Refresh Memories")
                    
                    with gr.Column(scale=1):
                        gr.Markdown("#### Add/Update Memory")
                        memory_type_dropdown = gr.Dropdown(
                            label="Memory Type",
                            choices=["core", "preference", "fact", "context", "custom"],
                            value="fact",
                        )
                        memory_key_input = gr.Textbox(
                            label="Key",
                            placeholder="e.g., favorite_color, job_title",
                        )
                        memory_value_input = gr.Textbox(
                            label="Value",
                            placeholder="e.g., blue, Software Engineer",
                            lines=2,
                        )
                        save_memory_btn = gr.Button("💾 Save Memory", variant="primary")
                        memory_status = gr.Textbox(label="Status", interactive=False)
                        
                        gr.Markdown("#### Delete Memory")
                        delete_key_input = gr.Textbox(
                            label="Key to Delete",
                            placeholder="Enter key name",
                        )
                        delete_memory_btn = gr.Button("🗑️ Delete Memory", variant="stop")
            
            # Activity Log Tab
            with gr.Tab("📊 Activity"):
                gr.Markdown(
                    """
                    ### Activity Log
                    
                    View recent interactions across all platforms (Web, Discord, Telegram).
                    Tool calls and messages are tracked here.
                    """
                )
                
                with gr.Row():
                    activity_platform_filter = gr.Dropdown(
                        label="Filter by Platform",
                        choices=["All", "web", "discord", "telegram", "cli"],
                        value="All",
                    )
                    refresh_activity_btn = gr.Button("🔄 Refresh Activity")
                
                activity_log = gr.Dataframe(
                    headers=["Time", "Platform", "User", "Role", "Content"],
                    datatype=["str", "str", "str", "str", "str"],
                    label="Recent Activity",
                    interactive=False,
                    row_count=15,
                )
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 🔧 Tool Usage Summary")
                        tool_usage_summary = gr.Textbox(
                            label="Tools used in recent sessions",
                            lines=5,
                            interactive=False,
                        )
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### 📋 Recent Tool Calls")
                        recent_tool_calls = gr.Textbox(
                            label="Detailed tool execution log",
                            lines=8,
                            interactive=False,
                        )
            
            # Settings Tab
            with gr.Tab("⚙️ Settings"):
                with gr.Accordion("🦙 Ollama Settings", open=True):
                    with gr.Row():
                        with gr.Column():
                            ollama_host = gr.Textbox(
                                label="Ollama Host",
                                value=settings.ollama.host,
                                placeholder="http://localhost:11434",
                            )
                            
                            temperature = gr.Slider(
                                label="Temperature",
                                minimum=0.0,
                                maximum=2.0,
                                step=0.1,
                                value=settings.ollama.temperature,
                            )
                            
                            max_tokens = gr.Number(
                                label="Max Tokens",
                                value=settings.ollama.max_tokens,
                            )
                
                with gr.Accordion("🔍 Model Discovery", open=False):
                    gr.Markdown(
                        """
                        ### Discover & Install Models
                        
                        Local Pigeon supports various model types:
                        - **🧠 Thinking/Reasoning**: Chain-of-thought models (DeepSeek R1, Qwen3, Kimi K2)
                        - **🖼️ Vision Models**: Can analyze images (llava, moondream, llama3.2-vision)
                        - **💻 Coding Models**: Optimized for code (Qwen Coder, CodeLlama, DeepSeek Coder)
                        - **💬 General Chat**: Well-rounded models (Gemma, Llama, Mistral)
                        - **⚡ Small/Fast**: Lightweight models for quick responses
                        """
                    )
                    
                    with gr.Tabs():
                        with gr.Tab("📦 Installed"):
                            models_list = gr.Dataframe(
                                headers=["Model", "Size", "Vision", "Status"],
                                datatype=["str", "str", "str", "str"],
                                label="Installed Models",
                                interactive=False,
                                row_count=5,
                            )
                            refresh_models_list_btn = gr.Button("🔄 Refresh")
                        
                        with gr.Tab("📚 Model Catalog"):
                            gr.Markdown("**Browse available models by category:**")
                            
                            catalog_category_filter = gr.Dropdown(
                                label="Filter by Category",
                                choices=[
                                    "All Models",
                                    "⭐ Recommended",
                                    "🧠 Thinking/Reasoning",
                                    "🖼️ Vision",
                                    "💻 Coding",
                                    "💬 General",
                                    "⚡ Small/Fast",
                                ],
                                value="⭐ Recommended",
                            )
                            
                            catalog_list = gr.Dataframe(
                                headers=["Model", "Size", "Type", "Backend", "Description"],
                                datatype=["str", "str", "str", "str", "str"],
                                label="Model Catalog",
                                interactive=False,
                                row_count=8,
                            )
                        
                        with gr.Tab("📥 Install Model"):
                            gr.Markdown(
                                """
                                **Install models via Ollama or GGUF (llama-cpp-python)**
                                
                                For **Ollama** (recommended): Enter model name like `deepseek-r1:7b`, `qwen3:8b`, `llava`
                                
                                For **GGUF**: Select from catalog or enter HuggingFace repo path
                                """
                            )
                            
                            install_backend = gr.Radio(
                                label="Backend",
                                choices=["Ollama (recommended)", "GGUF (llama-cpp-python)"],
                                value="Ollama (recommended)",
                            )
                            
                            pull_model_input = gr.Textbox(
                                label="Model Name",
                                placeholder="e.g., deepseek-r1:7b, qwen3:8b, llava",
                                info="Ollama: model name | GGUF: HuggingFace repo/file",
                            )
                            
                            with gr.Row():
                                pull_model_btn = gr.Button("📥 Install Model", variant="primary")
                                check_ollama_btn = gr.Button("🔍 Check Ollama Status")
                            
                            pull_model_status = gr.Textbox(
                                label="Status",
                                lines=3,
                                interactive=False,
                            )
                            
                            gr.Markdown(
                                """
                                ---
                                **Popular models to try:**
                                
                                | Model | Command | Best For |
                                |-------|---------|----------|
                                | DeepSeek R1 7B | `deepseek-r1:7b` | 🧠 Complex reasoning |
                                | Qwen 3 8B | `qwen3:8b` | 🧠 Thinking mode (/think) |
                                | LLaVA 7B | `llava:7b` | 🖼️ Image analysis |
                                | Moondream | `moondream` | 🖼️ Fast vision |
                                | Qwen Coder 7B | `qwen2.5-coder:7b` | 💻 Code generation |
                                | Llama 3.2 3B | `llama3.2:3b` | ⚡ Fast & capable |
                                | Gemma 3 4B | `gemma3:4b` | 💬 General chat |
                                """
                            )
                
                with gr.Accordion("� Agent Behavior (Ralph Loop)", open=False):
                    gr.Markdown(
                        "Configure how the agent executes tool loops. "
                        "[Learn about the Ralph Loop pattern](https://ghuntley.com/loop)"
                    )
                    with gr.Row():
                        with gr.Column():
                            checkpoint_mode = gr.Checkbox(
                                label="Checkpoint Mode",
                                value=settings.agent.checkpoint_mode,
                                info="Require approval before each tool execution (watch the loop)",
                            )
                            
                            max_tool_iterations = gr.Number(
                                label="Max Tool Iterations",
                                value=settings.agent.max_tool_iterations,
                                minimum=1,
                                maximum=50,
                                step=1,
                                info="Maximum tool calls per request before stopping",
                            )
                
                with gr.Accordion("�💳 Payment Settings", open=False):
                    with gr.Row():
                        with gr.Column():
                            payment_threshold = gr.Number(
                                label="Approval Threshold ($)",
                                value=settings.payments.approval.threshold,
                                info="Payments above this amount require approval",
                            )
                            
                            require_approval = gr.Checkbox(
                                label="Require Approval for All Payments",
                                value=settings.payments.approval.require_approval,
                            )
                
                with gr.Accordion("📁 Data Storage", open=False):
                    data_dir = ensure_data_dir()  # Ensure directory exists
                    gr.Markdown(
                        f"""
                        ### Your Data Location
                        
                        All your data is stored locally on your device at:
                        
                        📂 **`{data_dir}`**
                        
                        This includes:
                        - 💬 Conversations and chat history (`local_pigeon.db`)
                        - 🧠 Memories and preferences
                        - 🔑 Google OAuth tokens (`google_token.json`)
                        - ⚙️ Settings and configuration (`.env`)
                        """
                    )
                    with gr.Row():
                        open_folder_btn = gr.Button("📂 Open Data Folder", scale=2)
                        delete_data_btn = gr.Button("🗑️ Delete Local Data", variant="stop", scale=1)
                    
                    with gr.Row():
                        delete_config_too = gr.Checkbox(
                            label="Also delete configuration files (.env, credentials)",
                            value=False,
                            info="Check this to completely remove all data including settings",
                        )
                    
                    folder_status = gr.Textbox(label="Status", interactive=False, visible=True)
                
                save_settings_btn = gr.Button("💾 Save Settings", variant="primary")
                settings_status = gr.Textbox(label="Status", interactive=False)
            
            # Integrations Tab (renamed from OAuth Setup)
            with gr.Tab("🔗 Integrations"):
                gr.Markdown(
                    """
                    ### Connect Your Services
                    
                    Configure connections to external services like Discord, Telegram, and Google.
                    """
                )
                
                # Determine Discord status for accordion label
                _discord_label = "💬 Discord Bot"
                if settings.discord.bot_token:
                    _discord_label = "✅ Discord Bot"
                
                with gr.Accordion(_discord_label, open=True):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
                        2. Click **"New Application"** and name it
                        3. Go to **Bot** section → Click **"Add Bot"**
                        4. **Disable** "Requires OAuth2 Code Grant" (if enabled)
                        5. Enable **MESSAGE CONTENT INTENT** under Privileged Intents
                        6. Copy the **Bot Token** and **Application ID** (from General Information)
                        7. Generate the invite link below and add the bot to your server
                        """
                    )
                    discord_enabled = gr.Checkbox(
                        label="Enable Discord Bot",
                        value=settings.discord.enabled,
                    )
                    discord_token = gr.Textbox(
                        label="Bot Token",
                        type="password",
                        value=settings.discord.bot_token if settings.discord.bot_token else "",
                        placeholder="Paste your Discord bot token here",
                    )
                    discord_app_id = gr.Textbox(
                        label="Application ID (for invite link)",
                        value=settings.discord.app_id if settings.discord.app_id else "",
                        placeholder="Found on General Information page (e.g., 123456789012345678)",
                    )
                    discord_invite_url = gr.Textbox(
                        label="Bot Invite URL",
                        value="",
                        interactive=False,
                        placeholder="Enter Application ID above to generate invite link",
                    )
                    generate_invite_btn = gr.Button("🔗 Generate Invite Link")
                    discord_status = gr.Textbox(
                        label="Status",
                        value="✅ Configured" if settings.discord.bot_token else "⚠️ Not configured",
                        interactive=False,
                    )
                    with gr.Row():
                        save_discord_btn = gr.Button("💾 Save Discord Settings")
                        restart_discord_btn = gr.Button("🔄 Save & Restart App", variant="primary")
                
                # Determine Telegram status for accordion label
                _telegram_label = "📱 Telegram Bot"
                if settings.telegram.bot_token:
                    _telegram_label = "✅ Telegram Bot"
                
                with gr.Accordion(_telegram_label, open=False):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Open Telegram and search for **@BotFather**
                        2. Send `/newbot` command
                        3. Choose a name and username for your bot
                        4. Copy the token (looks like `123456:ABCdef...`)
                        """
                    )
                    telegram_enabled = gr.Checkbox(
                        label="Enable Telegram Bot",
                        value=settings.telegram.enabled,
                    )
                    telegram_token = gr.Textbox(
                        label="Bot Token",
                        type="password",
                        value=settings.telegram.bot_token if settings.telegram.bot_token else "",
                        placeholder="Paste your Telegram bot token here",
                    )
                    telegram_status = gr.Textbox(
                        label="Status",
                        value="✅ Configured" if settings.telegram.bot_token else "⚠️ Not configured",
                        interactive=False,
                    )
                    with gr.Row():
                        save_telegram_btn = gr.Button("💾 Save Telegram Settings")
                        restart_telegram_btn = gr.Button("🔄 Save & Restart App", variant="primary")
                
                # Determine Google status for accordion label
                _google_token_exists = (get_data_dir() / "google_token.json").exists()
                _google_label = "📧 Google Workspace"
                if _google_token_exists:
                    _google_label = "✅ Google Workspace"
                elif settings.google.credentials_path:
                    _google_label = "⚠️ Google Workspace (needs authorization)"
                
                with gr.Accordion(_google_label, open=False):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Go to [console.cloud.google.com](https://console.cloud.google.com)
                        2. Create a new project
                        3. Enable **Gmail**, **Calendar**, and **Drive** APIs
                        4. Create OAuth credentials (Desktop app)
                        5. Download the JSON file
                        6. **Upload** the file below, or enter the path manually
                        """
                    )
                    google_creds_upload = gr.File(
                        label="Upload credentials.json",
                        file_types=[".json"],
                        type="filepath",
                    )
                    google_creds_path = gr.Textbox(
                        label="Or enter path manually",
                        value=settings.google.credentials_path if settings.google.credentials_path else "",
                        placeholder="Path to your credentials.json file",
                    )
                    
                    gr.Markdown("**Enable Services:**")
                    with gr.Row():
                        google_gmail_enabled = gr.Checkbox(
                            label="Gmail",
                            value=settings.google.gmail_enabled,
                        )
                        google_calendar_enabled = gr.Checkbox(
                            label="Calendar",
                            value=settings.google.calendar_enabled,
                        )
                        google_drive_enabled = gr.Checkbox(
                            label="Drive",
                            value=settings.google.drive_enabled,
                        )
                    
                    google_status = gr.Textbox(
                        label="Status",
                        value="✅ Credentials uploaded" if settings.google.credentials_path else "⚠️ Upload credentials.json first",
                        interactive=False,
                    )
                    with gr.Row():
                        save_google_btn = gr.Button("💾 Save Google Settings")
                        authorize_google_btn = gr.Button("🔑 Authorize with Google", variant="primary")
                        test_google_btn = gr.Button("🧪 Test Connection")
                    
                    google_auth_info = gr.Markdown(
                        value="",
                        visible=False,
                    )
                
                # Determine Stripe status for accordion label
                _stripe_label = "💳 Stripe Payments"
                if settings.payments.stripe.api_key:
                    _stripe_label = "✅ Stripe Payments"
                
                with gr.Accordion(_stripe_label, open=False):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Go to [dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys)
                        2. Copy your **Secret Key** (starts with `sk_`)
                        """
                    )
                    stripe_enabled = gr.Checkbox(
                        label="Enable Stripe Payments",
                        value=settings.payments.stripe.enabled,
                    )
                    stripe_key_input = gr.Textbox(
                        label="Stripe Secret Key",
                        type="password",
                        value=settings.payments.stripe.api_key if settings.payments.stripe.api_key else "",
                        placeholder="sk_...",
                    )
                    stripe_status = gr.Textbox(
                        label="Status",
                        value="✅ Configured" if settings.payments.stripe.api_key else "⚠️ Not configured",
                        interactive=False,
                    )
                    save_stripe_btn = gr.Button("💾 Save Stripe Settings")
            
            # Tools Tab
            with gr.Tab("🧰 Tools"):
                gr.Markdown("### Available Tools")
                
                tools_table = gr.Dataframe(
                    headers=["Tool", "Description", "Enabled"],
                    datatype=["str", "str", "bool"],
                    value=[
                        ["Web Search", "Search the web using DuckDuckGo", settings.web.search.enabled],
                        ["Web Fetch", "Fetch and extract content from web pages", settings.web.fetch.enabled],
                        ["Browser", "Navigate dynamic websites (Google Flights, etc.)", settings.web.browser.enabled],
                        ["Gmail", "Read and send emails", settings.google.gmail_enabled],
                        ["Calendar", "Manage Google Calendar events", settings.google.calendar_enabled],
                        ["Drive", "Access Google Drive files", settings.google.drive_enabled],
                        ["Stripe Payments", "Make payments with virtual card", settings.payments.stripe.enabled],
                        ["Crypto Wallet", "Manage crypto payments", settings.payments.crypto.enabled],
                    ],
                    interactive=False,
                )
                
                with gr.Accordion("🌐 Browser Automation (Playwright)", open=True):
                    gr.Markdown(
                        """
                        **Browser automation** allows the AI to navigate websites that require JavaScript,
                        fill forms, and extract data from dynamic content (like Google Flights prices).
                        
                        **First-time setup:** Run `playwright install chromium` after enabling.
                        """
                    )
                    with gr.Row():
                        browser_enabled = gr.Checkbox(
                            label="Enable Browser Automation",
                            value=settings.web.browser.enabled,
                        )
                        browser_headless = gr.Checkbox(
                            label="Headless Mode (no visible window)",
                            value=settings.web.browser.headless,
                            info="Uncheck to see the browser window during automation",
                        )
                    
                    browser_status = gr.Textbox(
                        label="Status",
                        value="✅ Enabled (headless)" if settings.web.browser.enabled and settings.web.browser.headless 
                              else "✅ Enabled (GUI mode)" if settings.web.browser.enabled 
                              else "⚠️ Disabled",
                        interactive=False,
                    )
                    
                    with gr.Row():
                        save_browser_btn = gr.Button("💾 Save Browser Settings", variant="primary")
                        install_playwright_btn = gr.Button("📦 Install Playwright")
            
            # Documentation Tab
            with gr.Tab("📚 Docs"):
                with gr.Tabs():
                    with gr.Tab("Getting Started"):
                        gr.Markdown(
                            """
                            ## Getting Started with Local Pigeon
                            
                            Local Pigeon is your personal AI assistant that runs entirely on your device.
                            All your data stays local - nothing is sent to external servers.
                            
                            ### Quick Start
                            
                            1. **Chat**: Just type in the Chat tab and press Enter
                            2. **Tools**: The AI can search the web, manage emails, and more
                            3. **Memory**: Local Pigeon remembers things about you over time
                            4. **Integrations**: Connect Discord, Telegram, or Google services
                            
                            ### LLM Backends
                            
                            Local Pigeon supports two backends:
                            
                            | Backend | Description |
                            |---------|-------------|
                            | **Ollama** | Recommended. Install from [ollama.ai](https://ollama.ai) |
                            | **llama-cpp-python** | Fallback. Auto-downloads models from HuggingFace |
                            
                            The system automatically detects which backend is available.
                            
                            ### Data Storage
                            
                            Your data is stored locally:
                            - **Windows:** `%LOCALAPPDATA%\\LocalPigeon`
                            - **macOS:** `~/Library/Application Support/LocalPigeon`
                            - **Linux:** `~/.local/share/local_pigeon`
                            """
                        )
                    
                    with gr.Tab("Adding Tools"):
                        gr.Markdown(
                            '''
                            ## Creating Custom Tools
                            
                            Tools give Local Pigeon new capabilities. Here's how to create your own:
                            
                            ### 1. Create a Tool File
                            
                            Create a new file in `src/local_pigeon/tools/` (e.g., `my_tool.py`):
                            
                            ```python
                            """My Custom Tool"""
                            
                            from dataclasses import dataclass, field
                            from typing import Any
                            
                            from local_pigeon.tools.registry import Tool
                            
                            
                            @dataclass
                            class MyTool(Tool):
                                """A custom tool that does something useful."""
                                
                                settings: Any = field(default=None)
                                
                                def __post_init__(self):
                                    # Initialize your tool here
                                    pass
                                
                                @property
                                def name(self) -> str:
                                    return "my_custom_tool"
                                
                                @property
                                def description(self) -> str:
                                    return "Description of what this tool does"
                                
                                @property
                                def parameters(self) -> dict:
                                    return {
                                        "type": "object",
                                        "properties": {
                                            "input_text": {
                                                "type": "string",
                                                "description": "The input to process"
                                            }
                                        },
                                        "required": ["input_text"]
                                    }
                                
                                async def execute(self, **kwargs) -> str:
                                    """Execute the tool with given parameters."""
                                    input_text = kwargs.get("input_text", "")
                                    
                                    # Your tool logic here
                                    result = f"Processed: {input_text}"
                                    
                                    return result
                            ```
                            
                            ### 2. Register the Tool
                            
                            Add your tool to the agent's `_register_default_tools()` method in 
                            `src/local_pigeon/core/agent.py`:
                            
                            ```python
                            from local_pigeon.tools.my_tool import MyTool
                            
                            # In _register_default_tools():
                            self.tools.register(MyTool())
                            ```
                            
                            ### 3. Tool Best Practices
                            
                            - **Clear descriptions**: The AI uses these to decide when to use your tool
                            - **Specific parameters**: Define exactly what inputs your tool needs
                            - **Error handling**: Return helpful error messages
                            - **Async execution**: Use `async def execute()` for I/O operations
                            
                            ### Example Tools
                            
                            Look at existing tools for reference:
                            - `tools/web/search.py` - Web search
                            - `tools/web/fetch.py` - Fetch web pages
                            - `tools/google/gmail.py` - Email integration
                            '''
                        )
                    
                    with gr.Tab("Adding Integrations"):
                        gr.Markdown(
                            '''
                            ## Creating Platform Integrations
                            
                            Integrations let users interact with Local Pigeon through different platforms.
                            
                            ### Platform Adapter Pattern
                            
                            Create a new file in `src/local_pigeon/platforms/` (e.g., `slack_adapter.py`):
                            
                            ```python
                            """Slack Integration"""
                            
                            import asyncio
                            from local_pigeon.platforms.base import PlatformAdapter
                            from local_pigeon.core.agent import LocalPigeonAgent
                            
                            
                            class SlackAdapter(PlatformAdapter):
                                """Adapter for Slack integration."""
                                
                                def __init__(self, agent: LocalPigeonAgent, settings):
                                    self.agent = agent
                                    self.settings = settings
                                    self.client = None  # Your Slack client
                                
                                async def start(self):
                                    """Start the Slack bot."""
                                    # Initialize Slack client
                                    # Set up event handlers
                                    # Run the event loop
                                    pass
                                
                                async def stop(self):
                                    """Stop the Slack bot."""
                                    pass
                                
                                async def handle_message(self, message: str, user_id: str):
                                    """Handle incoming message."""
                                    response = await self.agent.chat(
                                        user_message=message,
                                        user_id=f"slack_{user_id}",
                                        platform="slack",
                                    )
                                    return response
                            ```
                            
                            ### Adding Settings
                            
                            Add settings to `src/local_pigeon/config.py`:
                            
                            ```python
                            class SlackSettings(BaseSettings):
                                """Slack bot settings."""
                                
                                enabled: bool = Field(default=False)
                                bot_token: str | None = Field(default=None)
                                app_token: str | None = Field(default=None)
                                
                                model_config = SettingsConfigDict(env_prefix="SLACK_")
                            ```
                            
                            ### Running the Integration
                            
                            Add to the CLI run command in `src/local_pigeon/cli.py`:
                            
                            ```python
                            if settings.slack.enabled and settings.slack.bot_token:
                                from local_pigeon.platforms.slack_adapter import SlackAdapter
                                tasks.append(SlackAdapter(agent, settings.slack).start())
                            ```
                            '''
                        )
                    
                    with gr.Tab("Configuration"):
                        gr.Markdown(
                            """
                            ## Configuration Options
                            
                            Local Pigeon can be configured via environment variables or `config.yaml`.
                            
                            ### Environment Variables
                            
                            Create a `.env` file in your data directory:
                            
                            ```bash
                            # LLM Settings
                            OLLAMA_HOST=http://localhost:11434
                            OLLAMA_MODEL=gemma3:latest
                            OLLAMA_TEMPERATURE=0.7
                            
                            # Discord Bot
                            DISCORD_ENABLED=true
                            DISCORD_BOT_TOKEN=your_token_here
                            
                            # Telegram Bot
                            TELEGRAM_ENABLED=true
                            TELEGRAM_BOT_TOKEN=your_token_here
                            
                            # Google Workspace
                            GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
                            
                            # Payments
                            STRIPE_ENABLED=true
                            STRIPE_API_KEY=sk_...
                            PAYMENT_APPROVAL_THRESHOLD=25.00
                            ```
                            
                            ### config.yaml
                            
                            For more complex settings, use `config.yaml`:
                            
                            ```yaml
                            model:
                              name: gemma3:latest
                              temperature: 0.7
                              context_length: 8192
                            
                            agent:
                              system_prompt: |
                                You are a helpful assistant...
                              max_history_messages: 20
                            
                            payments:
                              approval:
                                threshold: 25.00
                                daily_limit: 100.00
                            ```
                            
                            ### Priority Order
                            
                            Settings are loaded in this order (later overrides earlier):
                            1. Defaults in code
                            2. `config.yaml`
                            3. `.env` file
                            4. System environment variables
                            """
                        )
                    
                    with gr.Tab("API Reference"):
                        gr.Markdown(
                            """
                            ## Key Classes and Functions
                            
                            ### LocalPigeonAgent
                            
                            The main agent class that orchestrates everything:
                            
                            ```python
                            from local_pigeon.core.agent import LocalPigeonAgent
                            from local_pigeon.config import Settings
                            
                            settings = Settings.load()
                            agent = LocalPigeonAgent(settings)
                            await agent.initialize()
                            
                            # Chat with the agent
                            response = await agent.chat(
                                user_message="Hello!",
                                user_id="user123",
                            )
                            ```
                            
                            ### Tool Registry
                            
                            Register and manage tools:
                            
                            ```python
                            from local_pigeon.tools.registry import ToolRegistry, Tool
                            
                            registry = ToolRegistry()
                            registry.register(MyTool())
                            
                            # Get all tools
                            tools = registry.get_all()
                            
                            # Execute a tool
                            result = await registry.execute("tool_name", param1="value")
                            ```
                            
                            ### Memory Manager
                            
                            Store and retrieve user memories:
                            
                            ```python
                            from local_pigeon.storage.memory import AsyncMemoryManager, MemoryType
                            
                            memory = AsyncMemoryManager(db_path="local_pigeon.db")
                            
                            # Store a memory
                            await memory.set_memory(
                                user_id="user123",
                                key="favorite_color",
                                value="blue",
                                memory_type=MemoryType.PREFERENCE,
                            )
                            
                            # Retrieve memories
                            memories = await memory.get_all_memories("user123")
                            ```
                            
                            ### Conversation Manager
                            
                            Manage conversation history:
                            
                            ```python
                            from local_pigeon.core.conversation import AsyncConversationManager
                            
                            conversations = AsyncConversationManager(db_path="local_pigeon.db")
                            
                            # Get or create a conversation
                            conv_id = await conversations.get_or_create_conversation(
                                user_id="user123",
                                platform="web",
                            )
                            
                            # Add a message
                            await conversations.add_message(conv_id, "user", "Hello!")
                            ```
                            """
                        )
            
            # About Tab
            with gr.Tab("ℹ️ About"):
                data_dir = get_data_dir()
                gr.Markdown(
                    f"""
                    ### Local Pigeon
                    
                    **Version:** 0.1.0
                    
                    A fully local AI agent powered by Ollama. Your data stays on your device.
                    
                    **Features:**
                    - 🧠 Local LLM inference via Ollama
                    - 🔧 Extensible tool system
                    - 💳 Payment capabilities (Stripe + Crypto)
                    - 📧 Google Workspace integration
                    - 🔐 Human-in-the-loop approvals
                    - 💬 Multi-platform support (Discord, Telegram, Web)
                    
                    **Current Model:** {settings.ollama.model}
                    
                    **Data Directory:** `{data_dir}`
                    
                    **Links:**
                    - [GitHub Repository](https://github.com/tradermichael/local_pigeon)
                    - [Ollama](https://ollama.ai)
                    """
                )
        
        # Event handlers
        async def chat(
            message: str,
            history: list[dict],
        ) -> tuple[str, list[dict]]:
            """Handle chat message."""
            if not message.strip():
                return "", history
            
            try:
                current_agent = await get_agent()
                
                # Collect response
                response_parts = []
                
                def stream_callback(chunk: str) -> None:
                    response_parts.append(chunk)
                
                response = await current_agent.chat(
                    user_message=message,
                    user_id="web_user",
                    session_id="web_session",
                    platform="web",
                    stream_callback=stream_callback,
                )
                
                # Update history with new message format
                history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response},
                ]
                
                return "", history
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": error_msg},
                ]
                return "", history
        
        async def clear_history() -> list:
            """Clear chat history."""
            try:
                current_agent = await get_agent()
                await current_agent.clear_history("web_user")
            except Exception:
                pass
            return []
        
        async def refresh_models() -> gr.Dropdown:
            """Refresh available models from Ollama with capability indicators."""
            try:
                import httpx
                from local_pigeon.core.llm_client import OllamaClient
                
                # Create a temporary client to check capabilities
                temp_client = OllamaClient(host=settings.ollama.host)
                
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{settings.ollama.host}/api/tags",
                        timeout=10.0,
                    )
                    data = resp.json()
                    
                    # Build model choices with capability indicators
                    model_choices = []
                    for m in data.get("models", []):
                        name = m["name"]
                        # Add vision indicator
                        if temp_client.is_vision_model(name):
                            display = f"🖼️ {name} (vision)"
                        else:
                            display = name
                        model_choices.append((display, name))
                    
                    if not model_choices:
                        model_choices = [(settings.ollama.model, settings.ollama.model)]
                    
                    # Get just the names for the value
                    choices = [c[1] for c in model_choices]
                    
                    return gr.Dropdown(
                        choices=model_choices,
                        value=choices[0] if choices else settings.ollama.model,
                    )
            except Exception:
                return gr.Dropdown(
                    choices=[settings.ollama.model],
                    value=settings.ollama.model,
                )
        
        async def change_model(model: str) -> None:
            """Change the active model and persist to settings."""
            try:
                current_agent = await get_agent()
                current_agent.set_model(model)
                # Persist to .env so it's remembered on restart
                _save_env_var("OLLAMA_MODEL", model)
            except Exception:
                pass
        
        async def list_installed_models() -> list:
            """List installed models with their capabilities."""
            try:
                import httpx
                from local_pigeon.core.llm_client import OllamaClient
                
                temp_client = OllamaClient(host=settings.ollama.host)
                
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{settings.ollama.host}/api/tags",
                        timeout=10.0,
                    )
                    data = resp.json()
                    
                    rows = []
                    for m in data.get("models", []):
                        name = m["name"]
                        size_bytes = m.get("size", 0)
                        size_gb = size_bytes / (1024 ** 3)
                        size_display = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{size_bytes / (1024 ** 2):.0f} MB"
                        
                        is_vision = temp_client.is_vision_model(name)
                        vision_display = "🖼️ Yes" if is_vision else "No"
                        
                        # Check if it's the current model
                        status = "✅ Active" if name == settings.ollama.model else "Available"
                        
                        rows.append([name, size_display, vision_display, status])
                    
                    return rows
            except Exception as e:
                return [[f"Error: {e}", "", "", ""]]
        
        async def pull_model(model_name: str, backend: str) -> str:
            """Pull/download a model from Ollama or HuggingFace."""
            if not model_name.strip():
                return "⚠️ Please enter a model name"
            
            model_name = model_name.strip()
            is_ollama = "Ollama" in backend
            
            if is_ollama:
                try:
                    import httpx
                    
                    # Check if Ollama is running
                    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                        try:
                            check = await client.get(f"{settings.ollama.host}/api/tags")
                            if check.status_code != 200:
                                return "❌ Ollama is not running. Start it with: `ollama serve`"
                        except Exception:
                            return "❌ Cannot connect to Ollama. Make sure it's running with: `ollama serve`"
                    
                    # Start pulling the model
                    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
                        resp = await client.post(
                            f"{settings.ollama.host}/api/pull",
                            json={"name": model_name, "stream": False},
                        )
                        
                        if resp.status_code == 200:
                            return f"✅ Successfully pulled {model_name}!\n\nRefresh the model list to see it, then select it from the dropdown."
                        else:
                            return f"❌ Failed to pull model: {resp.text}"
                            
                except Exception as e:
                    return f"❌ Error pulling model: {str(e)}"
            else:
                # GGUF download via llama-cpp-python
                try:
                    from local_pigeon.core.llama_cpp_client import download_model, AVAILABLE_MODELS
                    from local_pigeon.core.model_catalog import find_model
                    
                    # Check if it's in our catalog
                    catalog_model = find_model(model_name)
                    if catalog_model and catalog_model.gguf_repo:
                        model_name = f"{catalog_model.gguf_repo.split('/')[-1]}"
                    
                    # Check if it's a known model
                    if model_name.lower().replace("-", "_").replace(" ", "_") in AVAILABLE_MODELS:
                        key = model_name.lower().replace("-", "_").replace(" ", "_")
                        path = download_model(key)
                        return f"✅ Downloaded GGUF model to:\n{path}\n\nThe model is ready to use with llama-cpp-python backend."
                    elif "/" in model_name:
                        # Assume HuggingFace format: repo/filename.gguf
                        path = download_model(model_name)
                        return f"✅ Downloaded GGUF model to:\n{path}"
                    else:
                        available = ", ".join(AVAILABLE_MODELS.keys())
                        return f"❌ Unknown GGUF model: {model_name}\n\nAvailable: {available}\n\nOr use HuggingFace format: owner/repo/filename.gguf"
                        
                except ImportError:
                    return "❌ GGUF support requires:\n`pip install llama-cpp-python huggingface_hub`"
                except Exception as e:
                    return f"❌ Error downloading GGUF: {str(e)}"
        
        async def check_ollama_status() -> str:
            """Check if Ollama is running and get status."""
            try:
                import httpx
                
                async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                    resp = await client.get(f"{settings.ollama.host}/api/tags")
                    if resp.status_code == 200:
                        data = resp.json()
                        model_count = len(data.get("models", []))
                        return f"✅ Ollama is running at {settings.ollama.host}\n\n📦 {model_count} model(s) installed"
                    else:
                        return f"⚠️ Ollama responded but with status {resp.status_code}"
            except Exception as e:
                return f"❌ Ollama is not running or not reachable.\n\nStart it with: `ollama serve`\n\nError: {str(e)}"
        
        def load_model_catalog(category_filter: str) -> list:
            """Load model catalog filtered by category."""
            try:
                from local_pigeon.core.model_catalog import (
                    MODEL_CATALOG, ModelCategory,
                    get_recommended_models, get_thinking_models,
                    get_vision_models, get_coding_models,
                    get_small_models, get_models_by_category,
                )
                
                # Map filter to category
                if category_filter == "⭐ Recommended":
                    models = get_recommended_models()
                elif category_filter == "🧠 Thinking/Reasoning":
                    models = get_thinking_models()
                elif category_filter == "🖼️ Vision":
                    models = get_vision_models()
                elif category_filter == "💻 Coding":
                    models = get_coding_models()
                elif category_filter == "💬 General":
                    models = get_models_by_category(ModelCategory.GENERAL)
                elif category_filter == "⚡ Small/Fast":
                    models = get_small_models()
                else:
                    models = MODEL_CATALOG
                
                # Format for display
                rows = []
                for model in models:
                    # Format categories with emojis
                    cat_emojis = {
                        ModelCategory.THINKING: "🧠",
                        ModelCategory.VISION: "🖼️",
                        ModelCategory.CODING: "💻",
                        ModelCategory.GENERAL: "💬",
                        ModelCategory.SMALL: "⚡",
                        ModelCategory.MULTILINGUAL: "🌍",
                    }
                    categories = " ".join(cat_emojis.get(c, "") for c in model.categories)
                    
                    # Backend availability
                    backends = []
                    if model.supports_ollama:
                        backends.append("Ollama")
                    if model.supports_gguf:
                        backends.append("GGUF")
                    backend_str = " / ".join(backends)
                    
                    # Recommended indicator
                    name = f"⭐ {model.name}" if model.recommended else model.name
                    
                    rows.append([
                        name,
                        model.size_label,
                        categories,
                        backend_str,
                        model.description,
                    ])
                
                return rows
            except Exception as e:
                return [[f"Error: {e}", "", "", "", ""]]
        
        def save_settings_handler(
            host: str,
            temp: float,
            tokens: int,
            checkpoint_mode_val: bool,
            max_iterations_val: int,
            threshold: float,
            require_approval_val: bool,
        ) -> str:
            """Save settings to config."""
            try:
                # Update settings object
                settings.ollama.host = host
                settings.ollama.temperature = temp
                settings.ollama.max_tokens = int(tokens)
                settings.agent.checkpoint_mode = checkpoint_mode_val
                settings.agent.max_tool_iterations = int(max_iterations_val)
                settings.payments.approval.threshold = threshold
                settings.payments.approval.require_approval = require_approval_val
                
                return "✅ Settings saved successfully!"
            except Exception as e:
                return f"❌ Error saving settings: {str(e)}"
        
        def open_data_folder() -> str:
            """Open the data folder in file explorer."""
            try:
                data_dir = get_data_dir()
                if sys.platform == "win32":
                    os.startfile(data_dir)
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(data_dir)])
                else:
                    subprocess.run(["xdg-open", str(data_dir)])
                return "📂 Opened data folder"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def handle_delete_data(include_config: bool) -> str:
            """Delete local data with user confirmation."""
            nonlocal agent
            try:
                results = delete_local_data(keep_config=not include_config)
                
                # Build status message
                deleted = [k for k, v in results.items() if v is True]
                not_found = [k for k, v in results.items() if v is False]
                errors = [f"{k}: {v}" for k, v in results.items() if isinstance(v, str)]
                
                msg_parts = []
                if deleted:
                    msg_parts.append(f"✅ **Deleted:** {', '.join(deleted)}")
                if not_found:
                    msg_parts.append(f"ℹ️ **Not found:** {', '.join(not_found)}")
                if errors:
                    msg_parts.append(f"❌ **Errors:** {', '.join(errors)}")
                
                if not msg_parts:
                    return "ℹ️ No data to delete"
                
                # Reset agent to clear any cached data
                agent = None
                
                return "\\n".join(msg_parts) + "\\n\\n⚠️ Please restart the app to fully reset."
            except Exception as e:
                return f"❌ Error deleting data: {str(e)}"
        
        # Memory handlers
        async def load_memories() -> list:
            """Load all memories for display."""
            try:
                memories = await memory_manager.get_all_memories("web_user")
                return [
                    [m.memory_type.value, m.key, m.value, m.source]
                    for m in memories
                ]
            except Exception:
                return []
        
        async def save_memory(mem_type: str, key: str, value: str) -> tuple[list, str]:
            """Save a new memory."""
            if not key.strip() or not value.strip():
                return await load_memories(), "❌ Key and value are required"
            
            try:
                memory_type = MemoryType(mem_type)
                await memory_manager.set_memory(
                    user_id="web_user",
                    key=key.strip(),
                    value=value.strip(),
                    memory_type=memory_type,
                    source="user",
                )
                return await load_memories(), f"✅ Saved: {key}"
            except Exception as e:
                return await load_memories(), f"❌ Error: {str(e)}"
        
        async def delete_memory(key: str) -> tuple[list, str]:
            """Delete a memory."""
            if not key.strip():
                return await load_memories(), "❌ Key is required"
            
            try:
                deleted = await memory_manager.delete_memory("web_user", key.strip())
                if deleted:
                    return await load_memories(), f"✅ Deleted: {key}"
                else:
                    return await load_memories(), f"⚠️ Not found: {key}"
            except Exception as e:
                return await load_memories(), f"❌ Error: {str(e)}"
        
        # Voice transcription handler
        async def transcribe_audio(audio_path: str) -> tuple[str, str]:
            """Transcribe audio using Whisper via Ollama or local model."""
            if not audio_path:
                return "", ""
            
            try:
                # Try using OpenAI Whisper API locally if available
                # Or use a speech-to-text service
                import httpx
                
                # First, try Ollama's experimental audio support
                # Fall back to a simple local transcription approach
                try:
                    # Check if whisper is available via Ollama
                    async with httpx.AsyncClient() as client:
                        # Read audio file
                        with open(audio_path, "rb") as f:
                            audio_data = f.read()
                        
                        # Try speech recognition with SpeechRecognition library
                        try:
                            import speech_recognition as sr
                            recognizer = sr.Recognizer()
                            
                            with sr.AudioFile(audio_path) as source:
                                audio = recognizer.record(source)
                            
                            # Use Google's free speech recognition
                            text = recognizer.recognize_google(audio)
                            return text, text
                        except ImportError:
                            return "", "⚠️ Install speech_recognition: pip install SpeechRecognition"
                        except Exception as e:
                            return "", f"⚠️ Transcription error: {e}"
                
                except Exception as e:
                    return "", f"⚠️ Audio processing error: {e}"
            
            except Exception as e:
                return "", f"❌ Error: {str(e)}"
        
        async def send_voice_message(
            transcription: str,
            history: list[dict],
        ) -> tuple[str, list[dict], str]:
            """Send transcribed voice message as chat."""
            if not transcription.strip():
                return "", history, ""
            
            msg_result, new_history = await chat(transcription, history)
            return "", new_history, ""
        
        # Activity log handlers
        async def load_activity(platform_filter: str) -> tuple[list, str, str]:
            """Load recent activity across all platforms."""
            try:
                from local_pigeon.core.conversation import AsyncConversationManager
                import json
                
                conv_manager = AsyncConversationManager(db_path=settings.storage.database)
                
                platforms = None if platform_filter == "All" else [platform_filter]
                activity = await conv_manager.get_recent_activity(limit=50, platforms=platforms)
                
                # Format for display
                rows = []
                tool_usage = {}
                recent_tool_calls = []
                
                for item in activity:
                    # Parse timestamp
                    timestamp = item.get("timestamp", "")[:19] if item.get("timestamp") else ""
                    
                    # Track tool usage and recent calls
                    if item.get("tool_calls"):
                        try:
                            calls = json.loads(item["tool_calls"])
                            for call in calls:
                                tool_name = call.get("name", "unknown")
                                tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
                                
                                # Add to recent calls log
                                args_str = json.dumps(call.get("arguments", {}))
                                if len(args_str) > 80:
                                    args_str = args_str[:77] + "..."
                                recent_tool_calls.append(
                                    f"[{timestamp}] 🔧 {tool_name}({args_str})"
                                )
                        except Exception:
                            pass
                    
                    # Platform emoji
                    platform = item.get("platform", "")
                    platform_display = {
                        "web": "🌐 Web",
                        "discord": "💬 Discord",
                        "telegram": "📱 Telegram",
                        "cli": "💻 CLI",
                    }.get(platform, platform)
                    
                    rows.append([
                        timestamp,
                        platform_display,
                        item.get("user_id", "")[:20],
                        item.get("role", ""),
                        item.get("content", "")[:100] + ("..." if len(item.get("content", "")) > 100 else ""),
                    ])
                
                # Tool usage summary
                if tool_usage:
                    summary_lines = [f"• {name}: {count} calls" for name, count in sorted(tool_usage.items(), key=lambda x: -x[1])]
                    summary = "\n".join(summary_lines)
                else:
                    summary = "No tool usage recorded yet."
                
                # Recent tool calls log
                if recent_tool_calls:
                    recent_calls_text = "\n".join(recent_tool_calls[:20])  # Show last 20
                else:
                    recent_calls_text = "No recent tool calls."
                
                return rows, summary, recent_calls_text
            
            except Exception as e:
                return [], f"Error loading activity: {e}", ""
        
        # Integration handlers
        def generate_discord_invite(app_id: str) -> str:
            """Generate Discord bot invite URL."""
            if not app_id or not app_id.strip():
                return "⚠️ Enter your Application ID above"
            
            app_id = app_id.strip()
            if not app_id.isdigit():
                return "❌ Invalid Application ID (should be numbers only)"
            
            # Permissions bitmap:
            # - View Channels (1024)
            # - Send Messages (2048)
            # - Send Messages in Threads (274877906944)
            # - Embed Links (16384)
            # - Attach Files (32768)
            # - Add Reactions (64)
            # - Read Message History (65536)
            # - Use External Emojis (262144)
            # - Create Public Threads (34359738368)
            permissions = 309237981248
            
            invite_url = f"https://discord.com/api/oauth2/authorize?client_id={app_id}&permissions={permissions}&scope=bot%20applications.commands"
            return invite_url
        
        def save_discord_settings(enabled: bool, token: str, app_id: str) -> str:
            """Save Discord settings."""
            try:
                settings.discord.enabled = enabled
                settings.discord.bot_token = token
                # Save to .env file
                _save_env_var("DISCORD_ENABLED", str(enabled).lower())
                _save_env_var("DISCORD_BOT_TOKEN", token)
                if app_id:
                    _save_env_var("DISCORD_APP_ID", app_id)
                return "✅ Discord settings saved! Click 'Save & Restart' to apply."
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_telegram_settings(enabled: bool, token: str) -> str:
            """Save Telegram settings."""
            try:
                settings.telegram.enabled = enabled
                settings.telegram.bot_token = token
                _save_env_var("TELEGRAM_ENABLED", str(enabled).lower())
                _save_env_var("TELEGRAM_BOT_TOKEN", token)
                return "✅ Telegram settings saved! Click 'Save & Restart' to apply."
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_google_settings(uploaded_file: str | None, creds_path: str, gmail_enabled: bool, calendar_enabled: bool, drive_enabled: bool) -> str:
            """Save Google settings, handling uploaded file or manual path."""
            nonlocal agent
            try:
                final_path = creds_path
                
                # If a file was uploaded, copy it to the data directory
                if uploaded_file:
                    data_dir = get_data_dir()
                    dest_path = data_dir / "google_credentials.json"
                    
                    # Validate it's valid JSON with expected structure
                    try:
                        with open(uploaded_file, "r") as f:
                            creds_data = json.load(f)
                        # Check for expected OAuth credentials structure
                        if "installed" not in creds_data and "web" not in creds_data:
                            return "❌ Invalid credentials file. Expected OAuth client credentials from Google Cloud Console."
                    except json.JSONDecodeError:
                        return "❌ Invalid JSON file."
                    
                    # Copy file to data directory
                    shutil.copy2(uploaded_file, dest_path)
                    final_path = str(dest_path)
                
                if final_path and not Path(final_path).exists():
                    return f"❌ File not found: {final_path}"
                
                # Save enabled flags
                settings.google.gmail_enabled = gmail_enabled
                settings.google.calendar_enabled = calendar_enabled
                settings.google.drive_enabled = drive_enabled
                _save_env_var("GOOGLE_GMAIL_ENABLED", str(gmail_enabled).lower())
                _save_env_var("GOOGLE_CALENDAR_ENABLED", str(calendar_enabled).lower())
                _save_env_var("GOOGLE_DRIVE_ENABLED", str(drive_enabled).lower())
                
                if final_path:
                    settings.google.credentials_path = final_path
                    _save_env_var("GOOGLE_CREDENTIALS_PATH", final_path)
                
                # Reload agent tools if agent exists
                tools_reloaded = ""
                if agent is not None:
                    registered = agent.reload_tools()
                    enabled_tools = [t for t in registered if any(x in t.lower() for x in ["gmail", "calendar", "drive"])]
                    if enabled_tools:
                        tools_reloaded = f" Tools reloaded: {', '.join(enabled_tools)}"
                    else:
                        tools_reloaded = " (Google tools will be available after authorization)"
                
                if final_path:
                    return f"✅ Google settings saved!{tools_reloaded} Click 'Authorize with Google' to complete setup."
                else:
                    return f"✅ Google service settings saved!{tools_reloaded} Upload credentials.json to enable."
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def authorize_google() -> tuple:
            """Trigger Google OAuth authorization flow."""
            nonlocal agent
            creds_path = settings.google.credentials_path
            if not creds_path or not Path(creds_path).exists():
                return (
                    "❌ Upload credentials.json first",
                    gr.update(visible=True, value="**Error:** You need to upload your `credentials.json` file before authorizing.\n\n1. Upload the file above\n2. Click 'Save Google Settings'\n3. Then click 'Authorize with Google'")
                )
            
            try:
                # Import here to avoid circular imports
                from google_auth_oauthlib.flow import InstalledAppFlow
                
                # Combined scopes for all services (matching what tools use)
                SCOPES = [
                    # Gmail
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/gmail.send",
                    "https://www.googleapis.com/auth/gmail.modify",
                    # Calendar
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/calendar.events",
                    # Drive
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/drive.file",
                ]
                
                # Run OAuth flow - opens browser automatically and handles callback
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save token
                data_dir = get_data_dir()
                token_path = data_dir / "google_token.json"
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
                
                success_info = """### ✅ Authorization Complete!

**Your Google account is now connected.** Here's what you can do:

**Available Services:**
- 📧 **Gmail**: Read, search, and send emails
- 📅 **Calendar**: View and create events
- 📁 **Drive**: List, search, and read files

**Test it out:**
- Click the **🧪 Test Connection** button to verify everything works
- Or ask the AI: *"What's on my calendar today?"* or *"Show my recent emails"*

**Token saved to:** `{token_path}`
""".format(token_path=token_path)
                
                # Reload tools so Google tools are immediately available
                if agent is not None:
                    registered = agent.reload_tools()
                    google_tools = [t for t in registered if any(x in t.lower() for x in ["gmail", "calendar", "drive"])]
                    if google_tools:
                        success_info += f"\n**Tools loaded:** {', '.join(google_tools)}"
                
                return (
                    "✅ Google authorized successfully!",
                    gr.update(visible=True, value=success_info)
                )
            except Exception as e:
                error_info = f"""### ❌ Authorization Failed

**Error:** `{str(e)}`

**Troubleshooting:**
1. Make sure you complete the sign-in in your browser
2. Check that your OAuth credentials are for a "Desktop app" type
3. Ensure Gmail, Calendar, and Drive APIs are enabled in Google Cloud Console
4. Try uploading your credentials.json file again
"""
                return (
                    f"❌ Authorization failed: {str(e)}",
                    gr.update(visible=True, value=error_info)
                )
        
        def test_google_connection() -> tuple:
            """Test that Google services are accessible."""
            data_dir = get_data_dir()
            token_path = data_dir / "google_token.json"
            
            if not token_path.exists():
                return (
                    "⚠️ Not authorized yet",
                    gr.update(visible=True, value="**Not Authorized:** Click 'Authorize with Google' first to connect your account.")
                )
            
            results = []
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build
                
                creds = Credentials.from_authorized_user_file(str(token_path))
                
                # Direct links to enable each API
                API_ENABLE_LINKS = {
                    "Gmail": "https://console.cloud.google.com/apis/library/gmail.googleapis.com",
                    "Google Calendar": "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com",
                    "Google Drive": "https://console.cloud.google.com/apis/library/drive.googleapis.com",
                }
                
                def _format_google_error(e: Exception, service_name: str) -> str:
                    """Format Google API errors with helpful messages."""
                    err_str = str(e)
                    if "403" in err_str:
                        link = API_ENABLE_LINKS.get(service_name, "https://console.cloud.google.com/apis/library")
                        return f"API not enabled - [Enable {service_name} API]({link})"
                    elif "401" in err_str or "invalid_grant" in err_str.lower():
                        return "Token expired - click 'Authorize with Google' again"
                    elif "404" in err_str:
                        return "Resource not found"
                    else:
                        return err_str[:60]
                
                # Test Gmail
                if settings.google.gmail_enabled:
                    try:
                        service = build("gmail", "v1", credentials=creds)
                        profile = service.users().getProfile(userId="me").execute()
                        results.append(f"✅ **Gmail**: Connected as `{profile.get('emailAddress', 'unknown')}`")
                    except Exception as e:
                        results.append(f"❌ **Gmail**: {_format_google_error(e, 'Gmail')}")
                else:
                    results.append("⏸️ **Gmail**: Not enabled (check the Gmail checkbox above and save)")
                
                # Test Calendar
                if settings.google.calendar_enabled:
                    try:
                        service = build("calendar", "v3", credentials=creds)
                        calendar = service.calendars().get(calendarId="primary").execute()
                        results.append(f"✅ **Calendar**: Connected - {calendar.get('summary', 'Primary')}")
                    except Exception as e:
                        results.append(f"❌ **Calendar**: {_format_google_error(e, 'Google Calendar')}")
                else:
                    results.append("⏸️ **Calendar**: Not enabled (check the Calendar checkbox above and save)")
                
                # Test Drive
                if settings.google.drive_enabled:
                    try:
                        service = build("drive", "v3", credentials=creds)
                        about = service.about().get(fields="user").execute()
                        user = about.get("user", {})
                        results.append(f"✅ **Drive**: Connected as `{user.get('displayName', 'unknown')}`")
                    except Exception as e:
                        results.append(f"❌ **Drive**: {_format_google_error(e, 'Google Drive')}")
                else:
                    results.append("⏸️ **Drive**: Not enabled (check the Drive checkbox above and save)")
                
                all_ok = all("✅" in r for r in results if "⏸️" not in r)
                has_errors = any("❌" in r for r in results)
                
                if has_errors:
                    status = "❌ Some services failed"
                elif all_ok and not all("⏸️" in r for r in results):
                    status = "✅ All enabled services working!"
                else:
                    status = "⚠️ No services enabled"
                
                test_info = "### 🧪 Connection Test Results\n\n" + "\n".join(results)
                
                # Add helpful tips based on results
                if has_errors:
                    test_info += "\n\n**Troubleshooting:**\n"
                    if any("API not enabled" in r for r in results):
                        test_info += "- Click the links above to enable each API, or enable all at once:\n"
                        test_info += "  - [Enable Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com)\n"
                        test_info += "  - [Enable Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)\n"
                        test_info += "  - [Enable Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)\n"
                    if any("Token expired" in r for r in results):
                        test_info += "- Click 'Authorize with Google' to refresh your token\n"
                elif all_ok:
                    test_info += "\n\n**Ready to use!** Ask the AI to interact with your Google services."
                
                return (status, gr.update(visible=True, value=test_info))
                
            except Exception as e:
                return (
                    f"❌ Test failed: {str(e)}",
                    gr.update(visible=True, value=f"**Error loading credentials:** `{str(e)}`\n\nTry re-authorizing with Google.")
                )
        
        def save_stripe_settings(enabled: bool, api_key: str) -> str:
            """Save Stripe settings."""
            try:
                settings.payments.stripe.enabled = enabled
                settings.payments.stripe.api_key = api_key
                _save_env_var("STRIPE_ENABLED", str(enabled).lower())
                _save_env_var("STRIPE_API_KEY", api_key)
                return "✅ Stripe settings saved!"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_browser_settings(enabled: bool, headless: bool) -> str:
            """Save browser automation settings."""
            nonlocal agent
            try:
                settings.web.browser.enabled = enabled
                settings.web.browser.headless = headless
                _save_env_var("BROWSER_ENABLED", str(enabled).lower())
                _save_env_var("BROWSER_HEADLESS", str(headless).lower())
                
                # Reload agent tools to pick up the change
                if agent is not None:
                    agent.settings.web.browser.enabled = enabled
                    agent.settings.web.browser.headless = headless
                    agent.reload_tools()
                
                if enabled and headless:
                    status = "✅ Enabled (headless) - Tools reloaded"
                elif enabled:
                    status = "✅ Enabled (GUI mode) - Tools reloaded"
                else:
                    status = "⚠️ Disabled - Tools reloaded"
                
                return status
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def install_playwright() -> str:
            """Install Playwright and Chromium browser."""
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "playwright"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    return f"❌ pip install failed: {result.stderr}"
                
                # Install Chromium
                result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    return f"❌ Browser install failed: {result.stderr}"
                
                return "✅ Playwright and Chromium installed successfully!"
            except subprocess.TimeoutExpired:
                return "❌ Installation timed out. Try running manually: pip install playwright && playwright install chromium"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_and_restart_discord(enabled: bool, token: str, app_id: str) -> str:
            """Save Discord settings and restart the app."""
            save_discord_settings(enabled, token, app_id)
            return restart_app()
        
        def save_and_restart_telegram(enabled: bool, token: str) -> str:
            """Save Telegram settings and restart the app."""
            save_telegram_settings(enabled, token)
            return restart_app()
        
        def restart_app() -> str:
            """Restart the Local Pigeon application."""
            import sys
            import os
            
            # Schedule restart
            def do_restart():
                import time
                time.sleep(0.5)  # Brief delay to let response go through
                python = sys.executable
                os.execl(python, python, *sys.argv)
            
            import threading
            threading.Thread(target=do_restart, daemon=True).start()
            
            return "🔄 Restarting Local Pigeon... The page will refresh automatically."
        
        # Wire up events
        send_btn.click(
            fn=chat,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
        )
        
        msg_input.submit(
            fn=chat,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
        )
        
        clear_btn.click(
            fn=clear_history,
            outputs=[chatbot],
        )
        
        refresh_models_btn.click(
            fn=refresh_models,
            outputs=[model_dropdown],
        )
        
        model_dropdown.change(
            fn=change_model,
            inputs=[model_dropdown],
        )
        
        save_settings_btn.click(
            fn=save_settings_handler,
            inputs=[
                ollama_host,
                temperature,
                max_tokens,
                checkpoint_mode,
                max_tool_iterations,
                payment_threshold,
                require_approval,
            ],
            outputs=[settings_status],
        )
        
        # Model discovery events
        refresh_models_list_btn.click(
            fn=list_installed_models,
            outputs=[models_list],
        )
        
        pull_model_btn.click(
            fn=pull_model,
            inputs=[pull_model_input, install_backend],
            outputs=[pull_model_status],
        )
        
        check_ollama_btn.click(
            fn=check_ollama_status,
            outputs=[pull_model_status],
        )
        
        catalog_category_filter.change(
            fn=load_model_catalog,
            inputs=[catalog_category_filter],
            outputs=[catalog_list],
        )
        
        # Load catalog on app start
        app.load(
            fn=load_model_catalog,
            inputs=[catalog_category_filter],
            outputs=[catalog_list],
        )
        
        open_folder_btn.click(
            fn=open_data_folder,
            outputs=[folder_status],
        )
        
        delete_data_btn.click(
            fn=handle_delete_data,
            inputs=[delete_config_too],
            outputs=[folder_status],
        )
        
        # Memory events
        refresh_memories_btn.click(
            fn=load_memories,
            outputs=[memories_display],
        )
        
        save_memory_btn.click(
            fn=save_memory,
            inputs=[memory_type_dropdown, memory_key_input, memory_value_input],
            outputs=[memories_display, memory_status],
        )
        
        delete_memory_btn.click(
            fn=delete_memory,
            inputs=[delete_key_input],
            outputs=[memories_display, memory_status],
        )
        
        # Voice input events
        voice_input.change(
            fn=transcribe_audio,
            inputs=[voice_input],
            outputs=[msg_input, voice_status],
        )
        
        # Activity log events
        refresh_activity_btn.click(
            fn=load_activity,
            inputs=[activity_platform_filter],
            outputs=[activity_log, tool_usage_summary, recent_tool_calls],
        )
        
        activity_platform_filter.change(
            fn=load_activity,
            inputs=[activity_platform_filter],
            outputs=[activity_log, tool_usage_summary, recent_tool_calls],
        )
        
        # Integration events
        generate_invite_btn.click(
            fn=generate_discord_invite,
            inputs=[discord_app_id],
            outputs=[discord_invite_url],
        )
        
        save_discord_btn.click(
            fn=save_discord_settings,
            inputs=[discord_enabled, discord_token, discord_app_id],
            outputs=[discord_status],
        )
        
        restart_discord_btn.click(
            fn=save_and_restart_discord,
            inputs=[discord_enabled, discord_token, discord_app_id],
            outputs=[discord_status],
        )
        
        save_telegram_btn.click(
            fn=save_telegram_settings,
            inputs=[telegram_enabled, telegram_token],
            outputs=[telegram_status],
        )
        
        restart_telegram_btn.click(
            fn=save_and_restart_telegram,
            inputs=[telegram_enabled, telegram_token],
            outputs=[telegram_status],
        )
        
        save_google_btn.click(
            fn=save_google_settings,
            inputs=[google_creds_upload, google_creds_path, google_gmail_enabled, google_calendar_enabled, google_drive_enabled],
            outputs=[google_status],
        )
        
        authorize_google_btn.click(
            fn=authorize_google,
            outputs=[google_status, google_auth_info],
        )
        
        test_google_btn.click(
            fn=test_google_connection,
            outputs=[google_status, google_auth_info],
        )
        
        save_stripe_btn.click(
            fn=save_stripe_settings,
            inputs=[stripe_enabled, stripe_key_input],
            outputs=[stripe_status],
        )
        
        save_browser_btn.click(
            fn=save_browser_settings,
            inputs=[browser_enabled, browser_headless],
            outputs=[browser_status],
        )
        
        install_playwright_btn.click(
            fn=install_playwright,
            outputs=[browser_status],
        )
        
        # Load memories on startup
        app.load(
            fn=load_memories,
            outputs=[memories_display],
        )
    
    return app


def _save_env_var(key: str, value: str) -> None:
    """Save an environment variable to the .env file and current process."""
    import os
    
    # Set in current process immediately
    os.environ[key] = value
    
    data_dir = get_data_dir()
    env_path = data_dir / ".env"
    
    # Read existing
    existing = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing[k] = v
    
    # Update
    existing[key] = value
    
    # Write back
    with open(env_path, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")


def launch_ui(
    settings: Settings | None = None,
    share: bool = False,
    server_name: str = "127.0.0.1",
    server_port: int = 7860,
) -> None:
    """
    Launch the Gradio web UI.
    
    Args:
        settings: Application settings
        share: Create a public share link
        server_name: Server hostname
        server_port: Server port
    """
    app = create_app(settings)
    
    app.launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        show_error=True,
    )


if __name__ == "__main__":
    launch_ui()
