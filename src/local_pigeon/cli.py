"""
Local Pigeon CLI

Command-line interface for managing and running the Local Pigeon agent.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from local_pigeon import __version__
from local_pigeon.config import get_settings, get_data_dir

app = typer.Typer(
    name="local-pigeon",
    help="Local AI Agent with Discord/Telegram, Google Workspace & Payments",
    add_completion=False,
)
console = Console()


def print_banner():
    """Print the Local Pigeon banner."""
    banner = """
[cyan]  _                     _   ____  _                       
 | |    ___   ___ __ _| | |  _ \\(_) __ _  ___  ___  _ __  
 | |   / _ \\ / __/ _` | | | |_) | |/ _` |/ _ \\/ _ \\| '_ \\ 
 | |__| (_) | (_| (_| | | |  __/| | (_| |  __/ (_) | | | |
 |_____\\___/ \\___\\__,_|_| |_|   |_|\\__, |\\___|\___/|_| |_|
                                   |___/[/cyan]
    """
    console.print(banner)
    console.print(f"[dim]Version {__version__} - Local AI Agent[/dim]\n")


@app.command()
def run(
    host: str = typer.Option(None, "--host", "-h", help="Web UI host"),
    port: int = typer.Option(None, "--port", "-p", help="Web UI port"),
    no_ui: bool = typer.Option(False, "--no-ui", help="Disable web UI"),
    discord_only: bool = typer.Option(False, "--discord-only", help="Run Discord bot only"),
    telegram_only: bool = typer.Option(False, "--telegram-only", help="Run Telegram bot only"),
):
    """Start the Local Pigeon agent."""
    print_banner()
    
    settings = get_settings()
    
    # Override settings from CLI
    if host:
        settings.ui.host = host
    if port:
        settings.ui.port = port
    
    console.print("[green]Starting Local Pigeon...[/green]\n")
    
    # Check Ollama connection
    console.print("[dim]Checking Ollama connection...[/dim]")
    try:
        import ollama
        client = ollama.Client(host=settings.ollama.host)
        models = client.list()
        console.print(f"[green]✓[/green] Connected to Ollama at {settings.ollama.host}")
        console.print(f"[dim]  Available models: {', '.join(m['name'] for m in models.get('models', []))[:100]}...[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Could not connect to Ollama: {e}")
        console.print("[yellow]Make sure Ollama is running: ollama serve[/yellow]")
        raise typer.Exit(1)
    
    # Import and run the main application
    from local_pigeon.core.agent import LocalPigeonAgent
    
    async def main():
        agent = LocalPigeonAgent(settings)
        
        tasks = []
        
        # Start platforms
        if not telegram_only and settings.discord.enabled and settings.discord.bot_token:
            console.print("[green]✓[/green] Discord bot enabled")
            from local_pigeon.platforms.discord_adapter import DiscordAdapter
            discord_adapter = DiscordAdapter(agent, settings.discord)
            tasks.append(discord_adapter.start())
        
        if not discord_only and settings.telegram.enabled and settings.telegram.bot_token:
            console.print("[green]✓[/green] Telegram bot enabled")
            from local_pigeon.platforms.telegram_adapter import TelegramAdapter
            telegram_adapter = TelegramAdapter(agent, settings.telegram)
            tasks.append(telegram_adapter.start())
        
        # Start web UI
        if not no_ui and not discord_only and not telegram_only:
            console.print(f"[green]✓[/green] Web UI at http://{settings.ui.host}:{settings.ui.port}")
            from local_pigeon.ui.app import create_ui
            ui = create_ui(agent, settings)
            tasks.append(asyncio.to_thread(
                ui.launch,
                server_name=settings.ui.host,
                server_port=settings.ui.port,
                share=settings.ui.share,
                prevent_thread_lock=True,
            ))
        
        if not tasks:
            console.print("[yellow]No platforms enabled. Starting web UI only...[/yellow]")
            from local_pigeon.ui.app import create_ui
            ui = create_ui(agent, settings)
            ui.launch(
                server_name=settings.ui.host,
                server_port=settings.ui.port,
                share=settings.ui.share,
            )
        else:
            console.print("\n[green]Local Pigeon is running! Press Ctrl+C to stop.[/green]\n")
            await asyncio.gather(*tasks)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")


@app.command()
def setup():
    """Interactive setup wizard for Local Pigeon."""
    print_banner()
    
    console.print(Panel(
        "Welcome to Local Pigeon Setup!\n\n"
        "This wizard will help you configure your AI agent.",
        title="Setup Wizard",
        border_style="cyan",
    ))
    
    data_dir = get_data_dir()
    env_path = data_dir / ".env"
    
    console.print(f"\n[dim]Configuration will be saved to: {env_path}[/dim]\n")
    
    # Load existing settings if any
    existing_env = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    existing_env[key] = value
    
    new_env = dict(existing_env)
    
    # Ollama settings
    console.print("[bold cyan]1. Ollama Settings[/bold cyan]")
    ollama_host = Prompt.ask(
        "Ollama host",
        default=existing_env.get("OLLAMA_HOST", "http://localhost:11434")
    )
    new_env["OLLAMA_HOST"] = ollama_host
    
    ollama_model = Prompt.ask(
        "Default model",
        default=existing_env.get("OLLAMA_MODEL", "llama3.2")
    )
    new_env["OLLAMA_MODEL"] = ollama_model
    
    # Discord setup
    console.print("\n[bold cyan]2. Discord Bot (Optional)[/bold cyan]")
    if Confirm.ask("Enable Discord bot?", default=False):
        discord_token = Prompt.ask(
            "Discord bot token",
            default=existing_env.get("DISCORD_BOT_TOKEN", ""),
            password=True
        )
        new_env["DISCORD_BOT_TOKEN"] = discord_token
    
    # Telegram setup
    console.print("\n[bold cyan]3. Telegram Bot (Optional)[/bold cyan]")
    if Confirm.ask("Enable Telegram bot?", default=False):
        telegram_token = Prompt.ask(
            "Telegram bot token",
            default=existing_env.get("TELEGRAM_BOT_TOKEN", ""),
            password=True
        )
        new_env["TELEGRAM_BOT_TOKEN"] = telegram_token
    
    # Google Workspace setup
    console.print("\n[bold cyan]4. Google Workspace (Optional)[/bold cyan]")
    if Confirm.ask("Enable Google Workspace integration?", default=False):
        console.print("[dim]You'll need to set up OAuth credentials in Google Cloud Console.[/dim]")
        console.print("[dim]See: https://console.cloud.google.com/apis/credentials[/dim]")
        google_creds = Prompt.ask(
            "Path to credentials.json",
            default=existing_env.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        new_env["GOOGLE_CREDENTIALS_PATH"] = google_creds
    
    # Payment settings
    console.print("\n[bold cyan]5. Payment Settings[/bold cyan]")
    approval_threshold = Prompt.ask(
        "Payment approval threshold (USD)",
        default=existing_env.get("PAYMENT_APPROVAL_THRESHOLD", "25.00")
    )
    new_env["PAYMENT_APPROVAL_THRESHOLD"] = approval_threshold
    
    daily_limit = Prompt.ask(
        "Daily spending limit (USD)",
        default=existing_env.get("PAYMENT_DAILY_LIMIT", "100.00")
    )
    new_env["PAYMENT_DAILY_LIMIT"] = daily_limit
    
    # Save configuration
    console.print("\n[bold cyan]Saving configuration...[/bold cyan]")
    
    with open(env_path, "w") as f:
        f.write("# Local Pigeon Configuration\n")
        f.write("# Generated by setup wizard\n\n")
        for key, value in new_env.items():
            f.write(f"{key}={value}\n")
    
    console.print(f"[green]✓[/green] Configuration saved to {env_path}")
    
    # Offer to pull model
    console.print("\n[bold cyan]6. Model Setup[/bold cyan]")
    if Confirm.ask(f"Pull model '{ollama_model}' now?", default=True):
        console.print(f"[dim]Pulling {ollama_model}...[/dim]")
        import subprocess
        subprocess.run(["ollama", "pull", ollama_model])
    
    console.print("\n[green]Setup complete![/green]")
    console.print("\nRun [cyan]local-pigeon run[/cyan] to start the agent.\n")


@app.command()
def status():
    """Show the current status of Local Pigeon."""
    print_banner()
    
    settings = get_settings()
    
    table = Table(title="Local Pigeon Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")
    
    # Check Ollama
    try:
        import ollama
        client = ollama.Client(host=settings.ollama.host)
        models = client.list()
        model_names = [m["name"] for m in models.get("models", [])]
        table.add_row(
            "Ollama",
            "✓ Connected",
            f"{len(model_names)} models available"
        )
    except Exception as e:
        table.add_row("Ollama", "✗ Disconnected", str(e)[:50])
    
    # Check platforms
    if settings.discord.bot_token:
        table.add_row("Discord", "✓ Configured", "Token set")
    else:
        table.add_row("Discord", "○ Not configured", "")
    
    if settings.telegram.bot_token:
        table.add_row("Telegram", "✓ Configured", "Token set")
    else:
        table.add_row("Telegram", "○ Not configured", "")
    
    # Check Google
    creds_path = Path(settings.google.credentials_path)
    if creds_path.exists():
        table.add_row("Google Workspace", "✓ Credentials found", str(creds_path))
    else:
        table.add_row("Google Workspace", "○ Not configured", "")
    
    # Check payments
    if settings.payments.stripe.api_key:
        table.add_row("Stripe", "✓ Configured", "API key set")
    else:
        table.add_row("Stripe", "○ Not configured", "")
    
    if settings.payments.crypto.cdp_api_key_name:
        table.add_row("Crypto Wallet", "✓ Configured", "CDP key set")
    else:
        table.add_row("Crypto Wallet", "○ Not configured", "")
    
    # Settings summary
    table.add_row(
        "Approval Threshold",
        f"${settings.payments.approval.threshold:.2f}",
        f"Daily limit: ${settings.payments.approval.daily_limit:.2f}"
    )
    
    console.print(table)
    console.print()


@app.command()
def models():
    """List available Ollama models."""
    settings = get_settings()
    
    try:
        import ollama
        client = ollama.Client(host=settings.ollama.host)
        result = client.list()
        
        table = Table(title="Available Ollama Models")
        table.add_column("Name", style="cyan")
        table.add_column("Size", style="green")
        table.add_column("Modified", style="dim")
        
        for model in result.get("models", []):
            size_gb = model.get("size", 0) / (1024**3)
            table.add_row(
                model["name"],
                f"{size_gb:.1f} GB",
                model.get("modified_at", "")[:10]
            )
        
        console.print(table)
        
        console.print(f"\n[dim]Current default: {settings.ollama.model}[/dim]")
        console.print("[dim]Pull new models with: ollama pull <model>[/dim]\n")
        
    except Exception as e:
        console.print(f"[red]Error connecting to Ollama: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def chat(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """Start an interactive chat session in the terminal."""
    print_banner()
    
    settings = get_settings()
    if model:
        settings.ollama.model = model
    
    console.print(f"[dim]Using model: {settings.ollama.model}[/dim]")
    console.print("[dim]Type 'exit' or 'quit' to end the session.[/dim]\n")
    
    from local_pigeon.core.agent import LocalPigeonAgent
    
    agent = LocalPigeonAgent(settings)
    
    async def chat_loop():
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
                
                if user_input.lower() in ("exit", "quit", "q"):
                    console.print("[dim]Goodbye![/dim]")
                    break
                
                if not user_input.strip():
                    continue
                
                console.print("[bold green]Pigeon[/bold green]: ", end="")
                
                response = await agent.chat(user_input, user_id="cli")
                console.print(response)
                console.print()
                
            except KeyboardInterrupt:
                console.print("\n[dim]Goodbye![/dim]")
                break
    
    asyncio.run(chat_loop())


@app.command()
def version():
    """Show version information."""
    console.print(f"Local Pigeon v{__version__}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
