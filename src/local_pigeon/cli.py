"""
Local Pigeon CLI - Modern Terminal UI
"""

import asyncio
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.rule import Rule
from rich.align import Align
from rich.box import ROUNDED, DOUBLE, HEAVY, SIMPLE
from rich.text import Text
from rich.padding import Padding

from local_pigeon import __version__
from local_pigeon.config import get_settings, get_data_dir, ensure_data_dir
from local_pigeon.logging import setup_logging, get_recent_logs, list_log_files

app = typer.Typer(name="local-pigeon", help="Local AI Agent", add_completion=False)
console = Console()

# Ensure data directory exists on import
ensure_data_dir()

LOGO = """
[bold bright_cyan]╭─────────────────────────────────────────────────────────────────╮[/]
[bold bright_cyan]│[/]                                                                 [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [bold white]██╗      ██████╗  ██████╗ █████╗ ██╗     [/]                  [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [bold white]██║     ██╔═══██╗██╔════╝██╔══██╗██║     [/]                  [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [bold cyan]██║     ██║   ██║██║     ███████║██║     [/]                  [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [bold cyan]██║     ██║   ██║██║     ██╔══██║██║     [/]                  [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [dim cyan]███████╗╚██████╔╝╚██████╗██║  ██║███████╗[/]                  [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [dim cyan]╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝[/]                  [bold bright_cyan]│[/]
[bold bright_cyan]│[/]                                                                 [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [bold white]██████╗ ██╗ ██████╗ ███████╗ ██████╗ ███╗   ██╗[/]           [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [bold white]██╔══██╗██║██╔════╝ ██╔════╝██╔═══██╗████╗  ██║[/]           [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [bold cyan]██████╔╝██║██║  ███╗█████╗  ██║   ██║██╔██╗ ██║[/]           [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [bold cyan]██╔═══╝ ██║██║   ██║██╔══╝  ██║   ██║██║╚██╗██║[/]           [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [dim cyan]██║     ██║╚██████╔╝███████╗╚██████╔╝██║ ╚████║[/]           [bold bright_cyan]│[/]
[bold bright_cyan]│[/]   [dim cyan]╚═╝     ╚═╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝[/]           [bold bright_cyan]│[/]
[bold bright_cyan]│[/]                                                                 [bold bright_cyan]│[/]
[bold bright_cyan]│[/]              [bold yellow]�️[/] [italic bright_white]Your Local AI Assistant[/] [bold yellow]🕊️[/]               [bold bright_cyan]│[/]
[bold bright_cyan]│[/]                                                                 [bold bright_cyan]│[/]
[bold bright_cyan]╰─────────────────────────────────────────────────────────────────╯[/]
"""

LOGO_SMALL = """
[bold bright_cyan]╭──────────────────────────────────────────────╮[/]
[bold bright_cyan]│[/]  [bold yellow]�️[/] [bold bright_white]LOCAL PIGEON[/]  [dim]Your Local AI Assistant[/]  [bold bright_cyan]│[/]
[bold bright_cyan]╰──────────────────────────────────────────────╯[/]
"""

DISCORD_HELP = """
[bold bright_cyan]╭─ 📘 Discord Bot Setup ─────────────────────────────────────────╮[/]
[bold bright_cyan]│[/]                                                                [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 1:[/] Go to discord.com/developers/applications             [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 2:[/] Click [green]"New Application"[/] and name it                [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 3:[/] Go to [yellow]Bot[/] section → Click [green]"Add Bot"[/]                [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 4:[/] Click [green]"Copy"[/] under Token                            [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 5:[/] Enable [yellow]MESSAGE CONTENT INTENT[/]                       [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 6:[/] OAuth2 → URL Generator → Select [cyan]bot[/]                 [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 7:[/] Add permissions and invite bot                         [bold bright_cyan]│[/]
[bold bright_cyan]│[/]                                                                [bold bright_cyan]│[/]
[bold bright_cyan]╰────────────────────────────────────────────────────────────────╯[/]
"""

TELEGRAM_HELP = """
[bold bright_cyan]╭─ 📱 Telegram Bot Setup ────────────────────────────────────────╮[/]
[bold bright_cyan]│[/]                                                                [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 1:[/] Open Telegram and search for [cyan]@BotFather[/]              [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 2:[/] Send [green]/newbot[/] command                                [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 3:[/] Choose a name and username for your bot               [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 4:[/] Copy the token (looks like [dim]123456:ABCdef...[/])          [bold bright_cyan]│[/]
[bold bright_cyan]│[/]                                                                [bold bright_cyan]│[/]
[bold bright_cyan]╰────────────────────────────────────────────────────────────────╯[/]
"""

GOOGLE_HELP = """
[bold bright_cyan]╭─ 📧 Google Workspace Setup ────────────────────────────────────╮[/]
[bold bright_cyan]│[/]                                                                [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 1:[/] Go to console.cloud.google.com                        [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 2:[/] Create a new project                                  [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 3:[/] Enable [cyan]Gmail[/], [cyan]Calendar[/], [cyan]Drive[/] APIs                  [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 4:[/] Create OAuth credentials ([yellow]Desktop app[/])              [bold bright_cyan]│[/]
[bold bright_cyan]│[/]  [bold]Step 5:[/] Download and save as [green]credentials.json[/]               [bold bright_cyan]│[/]
[bold bright_cyan]│[/]                                                                [bold bright_cyan]│[/]
[bold bright_cyan]╰────────────────────────────────────────────────────────────────╯[/]
"""


def print_banner(small=False):
    console.clear()
    console.print(LOGO_SMALL if small else LOGO)
    console.print(Align.center(f"[dim]v{__version__} • Powered by Ollama • 100% Local[/dim]"))
    console.print()


def print_step_header(step, total, title, description=""):
    filled = "[bold green]━[/]" * step
    current = "[bold yellow]●[/]" if step < total else "[bold green]●[/]"
    empty = "[dim]─[/]" * (total - step)
    progress_bar = filled + current + empty
    
    console.print()
    console.print(f"[bold bright_cyan]┌─[/] [bold white]Step {step}/{total}[/] [bold bright_cyan]─────────────────────────────────────────────────┐[/]")
    console.print(f"[bold bright_cyan]│[/]  [bold bright_white]{title}[/]")
    if description:
        console.print(f"[bold bright_cyan]│[/]  [dim]{description}[/]")
    console.print(f"[bold bright_cyan]│[/]  {progress_bar}")
    console.print(f"[bold bright_cyan]└──────────────────────────────────────────────────────────────┘[/]")
    console.print()


def find_ollama():
    path = shutil.which("ollama")
    if path:
        return path
    if platform.system() == "Windows":
        for p in [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
                  os.path.expandvars(r"%PROGRAMFILES%\Ollama\ollama.exe")]:
            if os.path.exists(p):
                return p
    return None


def install_ollama():
    if platform.system() != "Windows":
        console.print("[yellow]Auto-install only on Windows. Visit https://ollama.ai[/yellow]")
        return None
    
    console.print(Panel(
        "[bold yellow]⚠ Ollama Not Found[/]\n\n"
        "Ollama is required for local AI inference.",
        border_style="yellow", box=ROUNDED,
    ))
    
    if not Confirm.ask("[bold]Install Ollama automatically?[/]", default=True):
        return None
    
    import urllib.request
    with Progress(SpinnerColumn(style="cyan"), TextColumn("[progress.description]{task.description}"),
                  BarColumn(complete_style="cyan"), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("[cyan]Downloading Ollama...[/]", total=100)
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = os.path.join(tmpdir, "OllamaSetup.exe")
            def report(bn, bs, ts):
                if ts > 0: progress.update(task, completed=min(100, (bn * bs * 100) // ts))
            urllib.request.urlretrieve("https://ollama.com/download/OllamaSetup.exe", installer, report)
            progress.update(task, completed=100, description="[green]Download complete![/]")
            console.print(Panel("[bold]Running installer...[/]", border_style="cyan"))
            subprocess.run([installer], shell=True)
    time.sleep(2)
    return find_ollama()


def ensure_ollama_running(ollama_path):
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        console.print("[dim]Ollama server already running[/]")
        return True
    except: pass
    console.print("[dim]Starting Ollama server...[/dim]")
    try:
        if platform.system() == "Windows":
            subprocess.Popen([ollama_path, "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen([ollama_path, "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for i in range(10):
            console.print(f"[dim]Waiting for Ollama to start... ({i+1}/10)[/]")
            time.sleep(1)
            try:
                urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
                console.print("[green]✓[/] Ollama server started!")
                return True
            except: continue
    except Exception as e:
        console.print(f"[yellow]⚠[/] Could not start: {e}")
    return False


def ask_with_help(prompt, default=False, help_key=None):
    default_hint = "[green]Y[/]/n" if default else "y/[green]N[/]"
    while True:
        r = Prompt.ask(f"{prompt} [dim][{default_hint}/?][/dim]", default="y" if default else "n").strip().lower()
        if r == "?":
            if help_key == "discord": console.print(DISCORD_HELP)
            elif help_key == "telegram": console.print(TELEGRAM_HELP)
            elif help_key == "google": console.print(GOOGLE_HELP)
            else: console.print("[dim]No help available.[/dim]")
            Prompt.ask("[dim]Press Enter to continue...[/dim]")
            continue
        if r in ("y", "yes"): return True
        if r in ("n", "no", ""): return r == "" and default
        console.print("[yellow]Enter y, n, or ? for help[/yellow]")


def prompt_with_help(prompt, default="", password=False):
    return Prompt.ask(f"[bold]{prompt}[/]", default=default, password=password)


def create_status_table(config):
    table = Table(box=SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Component", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Value", style="dim")
    
    ollama = find_ollama()
    table.add_row("🧠 Ollama", "[green]✓ Ready[/]" if ollama else "[yellow]○ Pending[/]", config.get("OLLAMA_MODEL", "gemma3:latest"))
    table.add_row("💬 Discord", "[green]✓ Configured[/]" if config.get("DISCORD_BOT_TOKEN") else "[dim]─ Skipped[/]", "")
    table.add_row("📱 Telegram", "[green]✓ Configured[/]" if config.get("TELEGRAM_BOT_TOKEN") else "[dim]─ Skipped[/]", "")
    table.add_row("📧 Google", "[green]✓ Configured[/]" if config.get("GOOGLE_CREDENTIALS_PATH") else "[dim]─ Skipped[/]", "")
    table.add_row("💳 Payments", "[green]✓ Configured[/]", f"Approval > ${config.get('PAYMENT_APPROVAL_THRESHOLD', '25.00')}")
    
    return Panel(table, title="[bold bright_white]📋 Configuration Summary[/]", border_style="bright_cyan", box=ROUNDED, padding=(1, 2))


@app.command()
def logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    level: Optional[str] = typer.Option(None, "--level", "-l", help="Filter by level (DEBUG, INFO, WARNING, ERROR)"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output (like tail -f)"),
    list_files: bool = typer.Option(False, "--list", help="List available log files"),
):
    """View recent logs for debugging."""
    if list_files:
        files = list_log_files()
        if not files:
            console.print("[yellow]No log files found.[/]")
            return
        table = Table(title="Log Files", box=ROUNDED)
        table.add_column("File", style="cyan")
        table.add_column("Size", style="dim")
        for f in files:
            size = f.stat().st_size
            size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
            table.add_row(f.name, size_str)
        console.print(table)
        return
    
    if follow:
        console.print("[dim]Following logs... Press Ctrl+C to stop[/]\n")
        data_dir = get_data_dir()
        log_dir = data_dir / "logs"
        from datetime import date
        log_file = log_dir / f"pigeon_{date.today().isoformat()}.log"
        if not log_file.exists():
            console.print(f"[yellow]No log file for today yet: {log_file}[/]")
            return
        try:
            import time as time_module
            with open(log_file, 'r') as f:
                # Go to end
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        console.print(line.rstrip())
                    else:
                        time_module.sleep(0.1)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped following logs.[/]")
            return
    
    log_output = get_recent_logs(lines=lines, level_filter=level)
    if not log_output.strip():
        console.print("[yellow]No logs found.[/] Run [cyan]pigeon run --debug[/] to enable debug logging.")
    else:
        console.print(log_output)


@app.command()
def run(host: str = None, port: int = None, no_ui: bool = False, debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging")):
    """Start the Local Pigeon agent."""
    print_banner(small=True)
    
    # Initialize logging
    log_level = "DEBUG" if debug else "INFO"
    logger = setup_logging(level=log_level, console=debug, debug_mode=debug)
    if debug:
        console.print("[yellow]Debug mode enabled - logging to console and file[/]")
    else:
        data_dir = get_data_dir()
        console.print(f"[dim]Logs: {data_dir / 'logs'}[/]")
    
    console.print("[dim]Initializing Local Pigeon...[/]")
    settings = get_settings()
    if host: settings.ui.host = host
    if port: settings.ui.port = port
    
    console.print("[dim]Looking for Ollama...[/]")
    ollama_path = find_ollama()
    if not ollama_path:
        console.print("[red]✗ Ollama not found.[/] Run [cyan]python -m local_pigeon setup[/] first.")
        raise typer.Exit(1)
    console.print(f"[dim]Found Ollama at: {ollama_path}[/]")
    
    console.print("[dim]Checking Ollama server status...[/]")
    if not ensure_ollama_running(ollama_path):
        console.print("[red]✗ Could not start Ollama.[/]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/] Ollama connected [dim]({settings.ollama.model})[/]")
    
    import signal
    shutdown_event = asyncio.Event()
    
    def handle_shutdown(signum, frame):
        console.print("\n[yellow]Shutting down Local Pigeon...[/yellow]")
        shutdown_event.set()
        # Force exit after brief delay if graceful shutdown fails
        import threading
        def force_exit():
            time.sleep(2)
            console.print("[dim]Force exiting...[/]")
            os._exit(0)
        threading.Thread(target=force_exit, daemon=True).start()
    
    from local_pigeon.core.agent import LocalPigeonAgent
    async def main():
        agent = LocalPigeonAgent(settings)
        await agent.initialize()
        
        # Track adapters for cleanup
        adapters = []
        tasks = []
        
        if settings.discord.enabled and settings.discord.bot_token:
            console.print("[green]✓[/] Discord bot enabled")
            from local_pigeon.platforms.discord_adapter import DiscordAdapter
            discord_adapter = DiscordAdapter(agent, settings.discord)
            adapters.append(discord_adapter)
            tasks.append(discord_adapter.start())
        if settings.telegram.enabled and settings.telegram.bot_token:
            console.print("[green]✓[/] Telegram bot enabled")
            from local_pigeon.platforms.telegram_adapter import TelegramAdapter
            telegram_adapter = TelegramAdapter(agent, settings.telegram)
            adapters.append(telegram_adapter)
            tasks.append(telegram_adapter.start())
        if not no_ui:
            ui_url = f"http://{settings.ui.host}:{settings.ui.port}"
            console.print(f"[green]✓[/] Web UI starting at {ui_url}")
            from local_pigeon.ui.app import launch_ui
            
            async def launch_ui_and_open_browser():
                # Small delay to let server start
                await asyncio.sleep(1.5)
                console.print(f"[dim]Opening browser to {ui_url}...[/]")
                webbrowser.open(ui_url)
            
            # Run UI in thread - it blocks until closed
            tasks.append(asyncio.to_thread(launch_ui, settings=settings, server_name=settings.ui.host, server_port=settings.ui.port))
            tasks.append(launch_ui_and_open_browser())
        if not tasks:
            from local_pigeon.ui.app import launch_ui
            ui_url = f"http://{settings.ui.host}:{settings.ui.port}"
            console.print(f"[dim]Opening browser to {ui_url}...[/]")
            webbrowser.open(ui_url)
            launch_ui(settings=settings)
        else:
            console.print()
            console.print(Panel("[bold green]🕊️ Local Pigeon is running![/]\n\nPress [bold]Ctrl+C[/] to stop.", border_style="green", box=ROUNDED))
            try:
                await asyncio.gather(*tasks, return_exceptions=False)
            except Exception as e:
                console.print(f"[red]Error: {e}[/]")
                import traceback
                traceback.print_exc()
            finally:
                # Cleanup adapters
                for adapter in adapters:
                    try:
                        await adapter.stop()
                    except Exception:
                        pass
                # Cleanup agent
                try:
                    await agent.shutdown()
                except Exception:
                    pass
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Signal handler already took care of shutdown message
    finally:
        console.print("[green]Goodbye! 🕊️[/]")
        sys.exit(0)


@app.command()
def setup():
    """Interactive setup wizard for Local Pigeon."""
    print_banner()
    console.print(Panel(
        "[bold bright_white]Welcome to Local Pigeon Setup![/]\n\n"
        "This wizard will configure your local AI assistant.\n"
        "Type [cyan]?[/] at any prompt for detailed help.",
        title="[bold yellow]�️ Setup Wizard[/]", border_style="bright_cyan", box=ROUNDED, padding=(1, 2),
    ))
    
    data_dir = get_data_dir()
    env_path = data_dir / ".env"
    console.print(f"\n  [dim]Config:[/] [cyan]{env_path}[/]\n")
    
    existing = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing[k] = v
    new_env = dict(existing)
    
    print_step_header(1, 6, "Ollama Configuration", "Local AI model settings")
    new_env["OLLAMA_HOST"] = prompt_with_help("Ollama host", default=existing.get("OLLAMA_HOST", "http://localhost:11434"))
    new_env["OLLAMA_MODEL"] = prompt_with_help("Default model", default=existing.get("OLLAMA_MODEL", "gemma3:latest"))
    console.print("[green]  ✓ Ollama settings saved[/]")
    
    print_step_header(2, 6, "Discord Bot", "Chat with your AI on Discord")
    if ask_with_help("Enable Discord bot?", default=False, help_key="discord"):
        new_env["DISCORD_BOT_TOKEN"] = prompt_with_help("Discord bot token", default=existing.get("DISCORD_BOT_TOKEN", ""), password=True)
        new_env["DISCORD_ENABLED"] = "true"
        console.print("[green]  ✓ Discord configured[/]")
    else:
        new_env["DISCORD_ENABLED"] = "false"
        console.print("[dim]  ○ Discord skipped[/]")
    
    print_step_header(3, 6, "Telegram Bot", "Chat with your AI on Telegram")
    if ask_with_help("Enable Telegram bot?", default=False, help_key="telegram"):
        new_env["TELEGRAM_BOT_TOKEN"] = prompt_with_help("Telegram bot token", default=existing.get("TELEGRAM_BOT_TOKEN", ""), password=True)
        new_env["TELEGRAM_ENABLED"] = "true"
        console.print("[green]  ✓ Telegram configured[/]")
    else:
        new_env["TELEGRAM_ENABLED"] = "false"
        console.print("[dim]  ○ Telegram skipped[/]")
    
    print_step_header(4, 6, "Google Workspace", "Gmail, Calendar, and Drive")
    if ask_with_help("Enable Google Workspace?", default=False, help_key="google"):
        new_env["GOOGLE_CREDENTIALS_PATH"] = prompt_with_help("Path to credentials.json", default=existing.get("GOOGLE_CREDENTIALS_PATH", "credentials.json"))
        new_env["GOOGLE_ENABLED"] = "true"
        console.print("[green]  ✓ Google Workspace configured[/]")
    else:
        new_env["GOOGLE_ENABLED"] = "false"
        console.print("[dim]  ○ Google Workspace skipped[/]")
    
    print_step_header(5, 6, "Payment Settings", "Spending limits and approvals")
    new_env["PAYMENT_APPROVAL_THRESHOLD"] = prompt_with_help("Approval threshold (USD)", default=existing.get("PAYMENT_APPROVAL_THRESHOLD", "25.00"))
    new_env["PAYMENT_DAILY_LIMIT"] = prompt_with_help("Daily spending limit (USD)", default=existing.get("PAYMENT_DAILY_LIMIT", "100.00"))
    console.print("[green]  ✓ Payment settings saved[/]")
    
    console.print()
    console.print(Rule("[bold bright_white]Saving Configuration[/]", style="bright_cyan"))
    console.print()
    
    with open(env_path, "w") as f:
        f.write(f"# Local Pigeon Configuration\n# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for k, v in new_env.items():
            f.write(f"{k}={v}\n")
    console.print(f"[green]✓[/] Saved to [cyan]{env_path}[/]")
    console.print()
    console.print(create_status_table(new_env))
    
    print_step_header(6, 6, "Ollama Installation", "Setting up the AI engine")
    ollama_path = find_ollama()
    if not ollama_path:
        ollama_path = install_ollama()
    else:
        console.print(f"[green]✓[/] Ollama found: [dim]{ollama_path}[/]")
    
    if ollama_path:
        ensure_ollama_running(ollama_path)
        model = new_env.get("OLLAMA_MODEL", "gemma3:latest")
        if ask_with_help(f"Download model '{model}'?", default=True):
            console.print()
            with Progress(SpinnerColumn(style="cyan"), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                task = progress.add_task(f"[cyan]Pulling {model}...[/]", total=None)
                result = subprocess.run([ollama_path, "pull", model], capture_output=True, text=True)
                if result.returncode == 0:
                    progress.update(task, description=f"[green]✓ {model} ready![/]")
                else:
                    console.print(f"[yellow]⚠[/] Run: [cyan]ollama pull {model}[/]")
    else:
        console.print("[yellow]⚠[/] Install Ollama from https://ollama.ai")
    
    console.print()
    console.print(Panel(
        "[bold green]🎉 Setup Complete![/]\n\n"
        "Start your AI assistant:\n  [cyan]python -m local_pigeon run[/]\n\n"
        "Or chat in terminal:\n  [cyan]python -m local_pigeon chat[/]",
        title="[bold bright_white]Ready to Go![/]", border_style="green", box=ROUNDED, padding=(1, 2),
    ))
    console.print()


@app.command()
def status():
    """Show the current status."""
    print_banner(small=True)
    settings = get_settings()
    table = Table(title="[bold bright_white]�️ Local Pigeon Status[/]", box=ROUNDED, border_style="bright_cyan", padding=(0, 2))
    table.add_column("Component", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")
    
    ollama = find_ollama()
    if ollama:
        try:
            import ollama as ol
            client = ol.Client(host=settings.ollama.host)
            models = client.list()
            table.add_row("🧠 Ollama", "[green]✓ Connected[/]", f"{len(models.get('models', []))} model(s)")
        except:
            table.add_row("🧠 Ollama", "[yellow]○ Not Running[/]", "ollama serve")
    else:
        table.add_row("🧠 Ollama", "[red]✗ Not Installed[/]", "ollama.ai")
    
    table.add_row("💬 Discord", "[green]✓ Configured[/]" if settings.discord.bot_token else "[dim]─ Not configured[/]", "")
    table.add_row("📱 Telegram", "[green]✓ Configured[/]" if settings.telegram.bot_token else "[dim]─ Not configured[/]", "")
    creds = Path(settings.google.credentials_path)
    table.add_row("📧 Google", "[green]✓ Ready[/]" if creds.exists() else "[dim]─ Not configured[/]", "")
    console.print(table)
    console.print()


@app.command()
def models():
    """List available Ollama models."""
    print_banner(small=True)
    settings = get_settings()
    try:
        import ollama
        client = ollama.Client(host=settings.ollama.host)
        result = client.list()
        table = Table(title="[bold bright_white]📦 Available Models[/]", box=ROUNDED, border_style="bright_cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Size", style="green", justify="right")
        table.add_column("Modified", style="dim")
        for m in result.get("models", []):
            table.add_row(m["name"], f"{m.get('size', 0) / (1024**3):.1f} GB", m.get("modified_at", "")[:10])
        console.print(table)
        console.print(f"\n[dim]Default: [cyan]{settings.ollama.model}[/][/]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")


@app.command()
def chat(model: Optional[str] = None):
    """Start an interactive chat session."""
    print_banner(small=True)
    settings = get_settings()
    if model: settings.ollama.model = model
    console.print(Panel(f"[dim]Model: [cyan]{settings.ollama.model}[/] • Type [yellow]exit[/] to quit[/]", border_style="dim", box=ROUNDED))
    console.print()
    
    from local_pigeon.core.agent import LocalPigeonAgent
    agent = LocalPigeonAgent(settings)
    async def loop():
        while True:
            try:
                user = Prompt.ask("[bold cyan]You[/]")
                if user.lower() in ("exit", "quit", "q"): break
                if not user.strip(): continue
                console.print("[bold green]�️ Pigeon[/]: ", end="")
                console.print(await agent.chat(user, user_id="cli"))
                console.print()
            except KeyboardInterrupt: break
        console.print("\n[dim]Goodbye! 👋[/]")
    asyncio.run(loop())


@app.command()
def eval(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to test"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Filter by tags (comma-separated)"),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save results to JSON file"),
):
    """Run tool usage evaluations."""
    import sys
    from pathlib import Path
    
    # Add project root to path so we can import evals
    project_root = Path(__file__).resolve().parents[3]  # src/local_pigeon/cli.py -> project root
    sys.path.insert(0, str(project_root))
    
    from evals import run_evals
    
    console.print(LOGO_SMALL)
    console.print("[bold]Running Tool Usage Evaluations[/]\n")
    
    tag_list = tags.split(",") if tags else None
    
    async def run():
        results = await run_evals(model=model, tags=tag_list, save_path=save)
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        
        if passed == total:
            console.print(f"\n[bold green]All {total} tests passed! 🎉[/]")
        else:
            console.print(f"\n[bold yellow]{passed}/{total} tests passed[/]")
    
    asyncio.run(run())


@app.command()
def version():
    """Show version information."""
    console.print(Panel(f"[bold bright_white]Local Pigeon[/] [cyan]v{__version__}[/]\n\n[dim]A fully local AI agent powered by Ollama[/]", border_style="bright_cyan", box=ROUNDED))


def main():
    app()

if __name__ == "__main__":
    main()
