"""
Diagnostic checks for Local Pigeon.

Provides `botf doctor` — a comprehensive health check that verifies
all services, dependencies, and configuration, with actionable fix hints.
Inspired by OpenClaw's `openclaw doctor` command.
"""

import asyncio
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    passed: bool
    message: str
    fix_hint: Optional[str] = None
    severity: str = "error"  # "error" | "warning" | "info"

    @property
    def icon(self) -> str:
        if self.passed:
            return "✅"
        return {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(self.severity, "❌")


@dataclass
class DoctorReport:
    """Aggregated diagnostic report."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == "warning")

    def format(self) -> str:
        """Format the report for terminal output."""
        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)

        lines = [
            "",
            "═" * 54,
            "  🕊️  Local Pigeon Doctor",
            f"  {passed}/{total} checks passed",
            "═" * 54,
            "",
        ]

        for check in self.checks:
            lines.append(f"  {check.icon} {check.name}: {check.message}")
            if not check.passed and check.fix_hint:
                lines.append(f"     💡 {check.fix_hint}")

        lines.append("")

        if self.passed:
            lines.append("  🎉 Everything looks good!")
        else:
            parts = []
            if self.error_count:
                parts.append(f"{self.error_count} error(s)")
            if self.warning_count:
                parts.append(f"{self.warning_count} warning(s)")
            lines.append(f"  ⚠️  {', '.join(parts)} found. See hints above.")

        lines.append("")
        return "\n".join(lines)


# ── Individual checks ──────────────────────────────────────────────


async def check_python_version() -> CheckResult:
    """Verify Python version meets minimum (3.10+)."""
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 10):
        return CheckResult("Python", True, version_str)
    return CheckResult(
        "Python",
        False,
        f"{version_str} (need 3.10+)",
        fix_hint="Install Python 3.10+ from python.org",
    )


async def check_ollama_running(host: str = "http://localhost:11434") -> CheckResult:
    """Check if Ollama is running and responsive."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{host}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get("models", []))
                return CheckResult("Ollama", True, f"Running ({count} model(s) installed)")
            return CheckResult(
                "Ollama",
                False,
                f"HTTP {resp.status_code}",
                fix_hint="Restart Ollama: `ollama serve`",
            )
    except httpx.ConnectError:
        return CheckResult(
            "Ollama",
            False,
            f"Not running at {host}",
            fix_hint="Start Ollama: `ollama serve`  — install from https://ollama.ai",
        )
    except Exception as e:
        return CheckResult("Ollama", False, str(e), fix_hint="Check Ollama installation")


async def check_models_installed(host: str = "http://localhost:11434") -> CheckResult:
    """Check that at least one chat model is pulled."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{host}/api/tags")
            models = resp.json().get("models", [])
            if models:
                names = [m["name"] for m in models[:5]]
                suffix = f" (+{len(models) - 5} more)" if len(models) > 5 else ""
                return CheckResult("Models", True, ", ".join(names) + suffix)
            return CheckResult(
                "Models",
                False,
                "No models installed",
                fix_hint="Pull a model: `ollama pull gemma3:latest`",
            )
    except Exception:
        return CheckResult(
            "Models",
            False,
            "Could not check (Ollama not running)",
            severity="warning",
        )


async def check_data_directory() -> CheckResult:
    """Verify data directory exists and is writable."""
    from local_pigeon.config import ensure_data_dir

    try:
        data_dir = ensure_data_dir()
        test_file = data_dir / ".doctor_probe"
        test_file.write_text("ok")
        test_file.unlink()
        return CheckResult("Data directory", True, str(data_dir))
    except Exception as e:
        return CheckResult(
            "Data directory",
            False,
            str(e),
            fix_hint="Check permissions on data directory",
        )


async def check_database() -> CheckResult:
    """Verify SQLite database is accessible."""
    from local_pigeon.config import get_data_dir, Settings

    settings = Settings.load()
    data_dir = get_data_dir()
    db_filename = settings.storage.database
    db_path = Path(db_filename) if Path(db_filename).is_absolute() else data_dir / db_filename

    if not db_path.exists():
        return CheckResult(
            "Database",
            True,
            "Will be created on first use",
            severity="info",
        )

    try:
        import aiosqlite

        async with aiosqlite.connect(str(db_path)) as db:
            async with db.execute("SELECT COUNT(*) FROM sqlite_master") as cur:
                row = await cur.fetchone()
                tables = row[0] if row else 0
            size_kb = db_path.stat().st_size / 1024
        return CheckResult("Database", True, f"{db_path.name} ({tables} tables, {size_kb:.0f} KB)")
    except Exception as e:
        return CheckResult(
            "Database",
            False,
            str(e),
            fix_hint=f"Remove corrupt DB: delete {db_path}",
        )


async def check_google_credentials() -> CheckResult:
    """Check Google OAuth credential/token status."""
    from local_pigeon.config import get_data_dir, Settings

    settings = Settings.load()
    data_dir = get_data_dir()
    token_path = data_dir / "google_token.json"
    creds_path = Path(settings.google.credentials_path)

    if token_path.exists():
        return CheckResult("Google OAuth", True, "Authorized (token present)")
    elif creds_path.exists():
        return CheckResult(
            "Google OAuth",
            True,
            "Credentials file found — not yet authorized",
            severity="warning",
            fix_hint="Authorize via Settings → Integrations → Google → Authorize",
        )
    return CheckResult(
        "Google OAuth",
        True,
        "Not configured (optional)",
        severity="info",
    )


async def check_discord() -> CheckResult:
    """Check Discord bot token presence."""
    from local_pigeon.config import Settings

    settings = Settings.load()
    if settings.discord.bot_token:
        return CheckResult("Discord", True, "Bot token set")
    return CheckResult("Discord", True, "Not configured (optional)", severity="info")


async def check_telegram() -> CheckResult:
    """Check Telegram bot token presence."""
    from local_pigeon.config import Settings

    settings = Settings.load()
    if settings.telegram.bot_token:
        return CheckResult("Telegram", True, "Bot token set")
    return CheckResult("Telegram", True, "Not configured (optional)", severity="info")


async def check_mcp_servers() -> CheckResult:
    """Check MCP server configuration."""
    from local_pigeon.config import Settings

    settings = Settings.load()
    servers = settings.mcp.servers if hasattr(settings.mcp, "servers") and settings.mcp.servers else []
    if servers:
        return CheckResult("MCP Servers", True, f"{len(servers)} configured")
    return CheckResult("MCP Servers", True, "None configured (optional)", severity="info")


async def check_optional_deps() -> list[CheckResult]:
    """Check optional Python dependencies."""
    results: list[CheckResult] = []

    # Playwright (browser automation)
    try:
        import playwright  # noqa: F401

        results.append(CheckResult("Playwright", True, "Installed"))
    except ImportError:
        results.append(
            CheckResult(
                "Playwright",
                True,
                "Not installed (optional)",
                severity="info",
                fix_hint="pip install playwright && playwright install chromium",
            )
        )

    # SpeechRecognition (voice input)
    try:
        import speech_recognition  # noqa: F401

        results.append(CheckResult("SpeechRecognition", True, "Installed"))
    except ImportError:
        results.append(
            CheckResult(
                "SpeechRecognition",
                True,
                "Not installed (optional)",
                severity="info",
                fix_hint="pip install SpeechRecognition",
            )
        )

    # Node.js (for MCP stdio servers)
    node = shutil.which("node")
    if node:
        import subprocess

        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            results.append(CheckResult("Node.js", True, f"{result.stdout.strip()} (for MCP)"))
        except Exception:
            results.append(CheckResult("Node.js", True, "Found but version check failed", severity="warning"))
    else:
        results.append(
            CheckResult(
                "Node.js",
                True,
                "Not installed (optional — needed for MCP servers)",
                severity="info",
                fix_hint="Install from https://nodejs.org",
            )
        )

    return results


async def check_log_directory() -> CheckResult:
    """Verify log directory is writable."""
    from local_pigeon.config import get_data_dir

    log_dir = get_data_dir() / "logs"
    if log_dir.exists():
        files = list(log_dir.glob("pigeon_*.log"))
        return CheckResult("Logs", True, f"{len(files)} log file(s) in {log_dir}")
    return CheckResult("Logs", True, "Log directory will be created on first run", severity="info")


# ── Orchestrator ───────────────────────────────────────────────────


async def run_doctor(host: str = "http://localhost:11434") -> DoctorReport:
    """Run all diagnostic checks and return a structured report."""
    report = DoctorReport()

    # Core checks
    report.checks.append(await check_python_version())
    report.checks.append(await check_ollama_running(host))
    report.checks.append(await check_models_installed(host))
    report.checks.append(await check_data_directory())
    report.checks.append(await check_database())
    report.checks.append(await check_log_directory())

    # Integration checks
    report.checks.append(await check_google_credentials())
    report.checks.append(await check_discord())
    report.checks.append(await check_telegram())
    report.checks.append(await check_mcp_servers())

    # Optional dependencies
    report.checks.extend(await check_optional_deps())

    return report
