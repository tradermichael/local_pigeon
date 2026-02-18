"""
Tests for the diagnostic (doctor) command.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from local_pigeon.diagnostics import (
    check_python_version,
    check_ollama_running,
    check_models_installed,
    check_data_directory,
    check_database,
    check_log_directory,
    check_google_credentials,
    check_discord,
    check_telegram,
    check_mcp_servers,
    check_optional_deps,
    run_doctor,
    CheckResult,
    DoctorReport,
)


# ── Unit: CheckResult / DoctorReport ──────────────────────────────


class TestCheckResult:
    def test_passed_icon(self):
        r = CheckResult("Test", True, "ok")
        assert r.icon == "✅"

    def test_error_icon(self):
        r = CheckResult("Test", False, "fail", severity="error")
        assert r.icon == "❌"

    def test_warning_icon(self):
        r = CheckResult("Test", False, "warn", severity="warning")
        assert r.icon == "⚠️"

    def test_info_icon(self):
        r = CheckResult("Test", False, "info", severity="info")
        assert r.icon == "ℹ️"


class TestDoctorReport:
    def test_all_passed(self):
        report = DoctorReport(checks=[
            CheckResult("A", True, "ok"),
            CheckResult("B", True, "ok"),
        ])
        assert report.passed
        assert report.error_count == 0

    def test_one_error(self):
        report = DoctorReport(checks=[
            CheckResult("A", True, "ok"),
            CheckResult("B", False, "fail", severity="error"),
        ])
        assert not report.passed
        assert report.error_count == 1

    def test_warning_only_still_passes(self):
        report = DoctorReport(checks=[
            CheckResult("A", True, "ok"),
            CheckResult("B", False, "warn", severity="warning"),
        ])
        assert report.passed
        assert report.warning_count == 1

    def test_format_contains_check_names(self):
        report = DoctorReport(checks=[
            CheckResult("Python", True, "3.11.0"),
            CheckResult("Ollama", False, "Not running", fix_hint="Start it"),
        ])
        text = report.format()
        assert "Python" in text
        assert "Ollama" in text
        assert "Start it" in text
        assert "1/2 checks passed" in text


# ── Unit: Individual checks ───────────────────────────────────────


class TestCheckPython:
    @pytest.mark.asyncio
    async def test_python_version_passes(self):
        """We're running on 3.10+, so this should always pass in CI."""
        result = await check_python_version()
        assert result.passed
        assert result.name == "Python"


class TestCheckOllama:
    @pytest.mark.asyncio
    async def test_ollama_running(self, mock_ollama_tags):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_ollama_tags)

        with patch("local_pigeon.diagnostics.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await check_ollama_running()
            assert result.passed
            assert "2 model(s)" in result.message

    @pytest.mark.asyncio
    async def test_ollama_not_running(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("local_pigeon.diagnostics.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await check_ollama_running()
            assert not result.passed
            assert result.fix_hint is not None


class TestCheckModels:
    @pytest.mark.asyncio
    async def test_models_present(self, mock_ollama_tags):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_ollama_tags)

        with patch("local_pigeon.diagnostics.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await check_models_installed()
            assert result.passed
            assert "gemma3" in result.message

    @pytest.mark.asyncio
    async def test_no_models(self):
        empty = MagicMock()
        empty.status_code = 200
        empty.json.return_value = {"models": []}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=empty)

        with patch("local_pigeon.diagnostics.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await check_models_installed()
            assert not result.passed
            assert "ollama pull" in result.fix_hint


class TestCheckDataDir:
    @pytest.mark.asyncio
    async def test_data_dir_ok(self, tmp_data_dir):
        with patch("local_pigeon.config.ensure_data_dir", return_value=tmp_data_dir):
            result = await check_data_directory()
            assert result.passed


class TestCheckLogDir:
    @pytest.mark.asyncio
    async def test_log_dir_exists(self, tmp_data_dir):
        with patch("local_pigeon.config.get_data_dir", return_value=tmp_data_dir):
            result = await check_log_directory()
            assert result.passed


class TestCheckGoogle:
    @pytest.mark.asyncio
    async def test_google_not_configured(self, tmp_data_dir):
        settings = MagicMock()
        settings.google.credentials_path = str(tmp_data_dir / "nonexistent.json")

        with patch("local_pigeon.config.get_data_dir", return_value=tmp_data_dir), \
             patch("local_pigeon.config.Settings.load", return_value=settings):
            result = await check_google_credentials()
            assert result.passed  # Not configured is OK (optional)
            assert "optional" in result.message.lower()


class TestCheckPlatforms:
    @pytest.mark.asyncio
    async def test_discord_not_configured(self):
        settings = MagicMock()
        settings.discord.bot_token = ""
        with patch("local_pigeon.config.Settings.load", return_value=settings):
            result = await check_discord()
            assert result.passed  # Optional
            assert "optional" in result.message.lower()

    @pytest.mark.asyncio
    async def test_telegram_not_configured(self):
        settings = MagicMock()
        settings.telegram.bot_token = ""
        with patch("local_pigeon.config.Settings.load", return_value=settings):
            result = await check_telegram()
            assert result.passed  # Optional

    @pytest.mark.asyncio
    async def test_discord_configured(self):
        settings = MagicMock()
        settings.discord.bot_token = "fake-token"
        with patch("local_pigeon.config.Settings.load", return_value=settings):
            result = await check_discord()
            assert result.passed
            assert "token set" in result.message.lower()


# ── Integration: full doctor report ───────────────────────────────


class TestRunDoctor:
    @pytest.mark.asyncio
    async def test_report_has_all_core_checks(self):
        """The report should contain at minimum: Python, Ollama, Models,
        Data directory, Database, Logs."""
        report = await run_doctor()
        names = [c.name for c in report.checks]
        assert "Python" in names
        assert "Ollama" in names
        assert "Models" in names
        assert "Data directory" in names
        assert "Database" in names
        assert "Logs" in names

    @pytest.mark.asyncio
    async def test_report_format_is_string(self):
        report = await run_doctor()
        text = report.format()
        assert isinstance(text, str)
        assert "Local Pigeon Doctor" in text
