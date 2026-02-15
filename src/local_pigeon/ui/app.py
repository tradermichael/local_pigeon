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
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Generator
import gradio as gr

from local_pigeon.config import Settings, get_data_dir


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
        settings = Settings()
    
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
        
        # Header
        gr.Markdown(
            """
            # 🕊️ Local Pigeon
            
            Your local AI assistant powered by Ollama. All processing happens on your device.
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
                
                with gr.Row():
                    clear_btn = gr.Button("🗑️ Clear History")
                    model_dropdown = gr.Dropdown(
                        label="Model",
                        choices=[settings.ollama.model],
                        value=settings.ollama.model,
                        interactive=True,
                    )
                    refresh_models_btn = gr.Button("🔄 Refresh Models")
                
                # Tool execution display
                with gr.Accordion("🔧 Tool Executions", open=False):
                    tool_log = gr.Textbox(
                        label="Recent Tool Calls",
                        lines=5,
                        interactive=False,
                    )
            
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
                
                with gr.Accordion("💳 Payment Settings", open=False):
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
                    data_dir = get_data_dir()
                    gr.Markdown(f"**Data Directory:** `{data_dir}`")
                    gr.Markdown(
                        """
                        Your conversations, memories, and settings are stored locally.
                        """
                    )
                    open_folder_btn = gr.Button("📂 Open Data Folder")
                    folder_status = gr.Textbox(label="", interactive=False, visible=False)
                
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
                
                with gr.Accordion("💬 Discord Bot", open=True):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
                        2. Click **"New Application"** and name it
                        3. Go to **Bot** section → Click **"Add Bot"**
                        4. Click **"Copy"** under Token
                        5. Enable **MESSAGE CONTENT INTENT**
                        6. Use OAuth2 → URL Generator to invite the bot to your server
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
                    discord_status = gr.Textbox(
                        label="Status",
                        value="✅ Configured" if settings.discord.bot_token else "⚠️ Not configured",
                        interactive=False,
                    )
                    save_discord_btn = gr.Button("💾 Save Discord Settings")
                
                with gr.Accordion("📱 Telegram Bot", open=False):
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
                    save_telegram_btn = gr.Button("💾 Save Telegram Settings")
                
                with gr.Accordion("📧 Google Workspace", open=False):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Go to [console.cloud.google.com](https://console.cloud.google.com)
                        2. Create a new project
                        3. Enable **Gmail**, **Calendar**, and **Drive** APIs
                        4. Create OAuth credentials (Desktop app)
                        5. Download the JSON file and save it
                        6. Enter the path to the file below
                        """
                    )
                    google_creds_path = gr.Textbox(
                        label="Credentials JSON Path",
                        value=settings.google.credentials_path if settings.google.credentials_path else "",
                        placeholder="Path to your credentials.json file",
                    )
                    google_status = gr.Textbox(
                        label="Status",
                        value="✅ Configured" if settings.google.credentials_path else "⚠️ Not configured",
                        interactive=False,
                    )
                    save_google_btn = gr.Button("💾 Save Google Settings")
                
                with gr.Accordion("💳 Stripe Payments", open=False):
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
                        ["Gmail", "Read and send emails", settings.google.gmail_enabled],
                        ["Calendar", "Manage Google Calendar events", settings.google.calendar_enabled],
                        ["Drive", "Access Google Drive files", settings.google.drive_enabled],
                        ["Stripe Payments", "Make payments with virtual card", settings.payments.stripe.enabled],
                        ["Crypto Wallet", "Manage crypto payments", settings.payments.crypto.enabled],
                    ],
                    interactive=False,
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
        ) -> tuple[str, list[dict], str]:
            """Handle chat message."""
            if not message.strip():
                return "", history, ""
            
            try:
                current_agent = await get_agent()
                
                # Collect response
                response_parts = []
                tool_calls_log = []
                
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
                
                return "", history, "\n".join(tool_calls_log)
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": error_msg},
                ]
                return "", history, ""
        
        async def clear_history() -> tuple[list, str]:
            """Clear chat history."""
            try:
                current_agent = await get_agent()
                await current_agent.clear_history("web_user")
            except Exception:
                pass
            return [], ""
        
        async def refresh_models() -> gr.Dropdown:
            """Refresh available models from Ollama."""
            try:
                import httpx
                
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{settings.ollama.host}/api/tags",
                        timeout=10.0,
                    )
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    
                    if not models:
                        models = [settings.ollama.model]
                    
                    return gr.Dropdown(choices=models, value=models[0])
            except Exception:
                return gr.Dropdown(
                    choices=[settings.ollama.model],
                    value=settings.ollama.model,
                )
        
        async def change_model(model: str) -> None:
            """Change the active model."""
            try:
                current_agent = await get_agent()
                current_agent.llm.model = model
            except Exception:
                pass
        
        def save_settings_handler(
            host: str,
            temp: float,
            tokens: int,
            threshold: float,
            require_approval_val: bool,
        ) -> str:
            """Save settings to config."""
            try:
                # Update settings object
                settings.ollama.host = host
                settings.ollama.temperature = temp
                settings.ollama.max_tokens = int(tokens)
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
        
        # Integration handlers
        def save_discord_settings(enabled: bool, token: str) -> str:
            """Save Discord settings."""
            try:
                settings.discord.enabled = enabled
                settings.discord.bot_token = token
                # Save to .env file
                _save_env_var("DISCORD_ENABLED", str(enabled).lower())
                _save_env_var("DISCORD_BOT_TOKEN", token)
                return "✅ Discord settings saved! Restart to apply."
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_telegram_settings(enabled: bool, token: str) -> str:
            """Save Telegram settings."""
            try:
                settings.telegram.enabled = enabled
                settings.telegram.bot_token = token
                _save_env_var("TELEGRAM_ENABLED", str(enabled).lower())
                _save_env_var("TELEGRAM_BOT_TOKEN", token)
                return "✅ Telegram settings saved! Restart to apply."
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_google_settings(creds_path: str) -> str:
            """Save Google settings."""
            try:
                if creds_path and not Path(creds_path).exists():
                    return f"❌ File not found: {creds_path}"
                settings.google.credentials_path = creds_path
                _save_env_var("GOOGLE_CREDENTIALS_PATH", creds_path)
                return "✅ Google settings saved!"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
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
        
        # Wire up events
        send_btn.click(
            fn=chat,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot, tool_log],
        )
        
        msg_input.submit(
            fn=chat,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot, tool_log],
        )
        
        clear_btn.click(
            fn=clear_history,
            outputs=[chatbot, tool_log],
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
                payment_threshold,
                require_approval,
            ],
            outputs=[settings_status],
        )
        
        open_folder_btn.click(
            fn=open_data_folder,
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
        
        # Integration events
        save_discord_btn.click(
            fn=save_discord_settings,
            inputs=[discord_enabled, discord_token],
            outputs=[discord_status],
        )
        
        save_telegram_btn.click(
            fn=save_telegram_settings,
            inputs=[telegram_enabled, telegram_token],
            outputs=[telegram_status],
        )
        
        save_google_btn.click(
            fn=save_google_settings,
            inputs=[google_creds_path],
            outputs=[google_status],
        )
        
        save_stripe_btn.click(
            fn=save_stripe_settings,
            inputs=[stripe_enabled, stripe_key_input],
            outputs=[stripe_status],
        )
        
        # Load memories on startup
        app.load(
            fn=load_memories,
            outputs=[memories_display],
        )
    
    return app


def _save_env_var(key: str, value: str) -> None:
    """Save an environment variable to the .env file."""
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
