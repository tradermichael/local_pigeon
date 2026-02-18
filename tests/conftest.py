"""
Shared test fixtures for Local Pigeon.

Provides isolated data directories, mock settings, and mock Ollama
for unit tests that don't need real services.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from local_pigeon.config import Settings


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Provide a temporary, isolated data directory for tests."""
    data_dir = tmp_path / "local_pigeon_test"
    data_dir.mkdir()
    (data_dir / "logs").mkdir()
    (data_dir / "models").mkdir()
    return data_dir


@pytest.fixture
def test_settings(tmp_data_dir: Path) -> Settings:
    """Provide Settings with an isolated data directory."""
    settings = Settings()
    settings.storage.database = str(tmp_data_dir / "test.db")
    return settings


@pytest.fixture
def mock_ollama_tags():
    """Mock httpx responses for Ollama /api/tags endpoint."""
    tags_response = MagicMock()
    tags_response.status_code = 200
    tags_response.json.return_value = {
        "models": [
            {"name": "gemma3:latest", "size": 5_000_000_000},
            {"name": "llama3.2:latest", "size": 4_000_000_000},
        ]
    }
    return tags_response
