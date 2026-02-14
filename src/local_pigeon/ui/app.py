"""
Gradio Web UI

Browser-based interface for Local Pigeon.
Provides:
- Chat interface with streaming
- Settings panel
- OAuth setup flows
- Tool execution display
"""

import asyncio
from typing import Any, Generator
import gradio as gr

from local_pigeon.config import Settings


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
    
    # Create agent instance
    agent: LocalPigeonAgent | None = None
    
    async def get_agent() -> LocalPigeonAgent:
        nonlocal agent
        if agent is None:
            agent = LocalPigeonAgent(settings)
            await agent.initialize()
        return agent
    
    # Theme configuration
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
    )
    
    with gr.Blocks(
        title="Local Pigeon",
        theme=theme,
        css="""
        .contain { display: flex; flex-direction: column; height: 100vh; }
        .chatbot { flex-grow: 1; overflow: auto; }
        footer { display: none !important; }
        """,
    ) as app:
        # State
        conversation_state = gr.State([])
        
        # Header
        gr.Markdown(
            """
            # 🐦 Local Pigeon
            
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
                    show_copy_button=True,
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
            
            # Settings Tab
            with gr.Tab("⚙️ Settings"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Ollama Settings")
                        
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
                    
                    with gr.Column():
                        gr.Markdown("### Payment Settings")
                        
                        payment_threshold = gr.Number(
                            label="Approval Threshold ($)",
                            value=settings.payments.approval_threshold,
                            info="Payments above this amount require approval",
                        )
                        
                        require_approval = gr.Checkbox(
                            label="Require Approval for All Payments",
                            value=settings.payments.require_approval,
                        )
                
                save_settings_btn = gr.Button("💾 Save Settings", variant="primary")
                settings_status = gr.Textbox(label="Status", interactive=False)
            
            # OAuth Tab
            with gr.Tab("🔐 OAuth Setup"):
                gr.Markdown(
                    """
                    ### Connect Your Accounts
                    
                    Set up OAuth connections to enable Google Workspace tools.
                    """
                )
                
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### Google Workspace")
                        google_status = gr.Textbox(
                            label="Status",
                            value="Not connected",
                            interactive=False,
                        )
                        google_connect_btn = gr.Button("🔗 Connect Google")
                        google_disconnect_btn = gr.Button("❌ Disconnect")
                    
                    with gr.Column():
                        gr.Markdown("#### Stripe")
                        stripe_status = gr.Textbox(
                            label="Status",
                            value="Not configured",
                            interactive=False,
                        )
                        stripe_key_input = gr.Textbox(
                            label="Stripe API Key",
                            type="password",
                            placeholder="sk_...",
                        )
                        stripe_save_btn = gr.Button("💾 Save")
            
            # Tools Tab
            with gr.Tab("🧰 Tools"):
                gr.Markdown("### Available Tools")
                
                tools_table = gr.Dataframe(
                    headers=["Tool", "Description", "Enabled"],
                    datatype=["str", "str", "bool"],
                    value=[
                        ["Web Search", "Search the web using DuckDuckGo", True],
                        ["Web Fetch", "Fetch and extract content from web pages", True],
                        ["Gmail", "Read and send emails", True],
                        ["Calendar", "Manage Google Calendar events", True],
                        ["Drive", "Access Google Drive files", True],
                        ["Stripe Payments", "Make payments with virtual card", True],
                        ["Crypto Wallet", "Manage crypto payments", True],
                    ],
                    interactive=False,
                )
            
            # About Tab
            with gr.Tab("ℹ️ About"):
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
                    
                    **Links:**
                    - [GitHub Repository](https://github.com/yourusername/local_pigeon)
                    - [Ollama](https://ollama.ai)
                    """
                )
        
        # Event handlers
        async def chat(
            message: str,
            history: list[tuple[str, str]],
        ) -> tuple[str, list[tuple[str, str]], str]:
            """Handle chat message."""
            if not message.strip():
                return "", history, ""
            
            try:
                current_agent = await get_agent()
                
                # Collect response
                response_parts = []
                tool_calls_log = []
                
                async def stream_callback(chunk: str):
                    response_parts.append(chunk)
                
                response = await current_agent.chat(
                    user_message=message,
                    user_id="web_user",
                    session_id="web_session",
                    platform="web",
                    stream_callback=stream_callback,
                )
                
                # Update history
                history = history + [(message, response)]
                
                return "", history, "\n".join(tool_calls_log)
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                history = history + [(message, error_msg)]
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
                current_agent.set_model(model)
            except Exception:
                pass
        
        def save_settings_handler(
            host: str,
            temp: float,
            tokens: int,
            threshold: float,
            require_approval: bool,
        ) -> str:
            """Save settings to config."""
            try:
                # Update settings object
                settings.ollama.host = host
                settings.ollama.temperature = temp
                settings.ollama.max_tokens = int(tokens)
                settings.payments.approval_threshold = threshold
                settings.payments.require_approval = require_approval
                
                return "✅ Settings saved successfully!"
            except Exception as e:
                return f"❌ Error saving settings: {str(e)}"
        
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
    
    return app


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
