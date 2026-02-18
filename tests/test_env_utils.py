"""
Tests for environment variable persistence (env_utils).
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from local_pigeon.ui.env_utils import save_env_var


class TestSaveEnvVar:
    def test_creates_env_file(self, tmp_data_dir):
        """Should create .env if it doesn't exist."""
        with patch("local_pigeon.ui.env_utils.get_data_dir", return_value=tmp_data_dir):
            save_env_var("TEST_KEY", "test_value")

        env_path = tmp_data_dir / ".env"
        assert env_path.exists()
        content = env_path.read_text()
        assert "TEST_KEY=test_value" in content

    def test_updates_existing_key(self, tmp_data_dir):
        """Should update existing key without duplicating."""
        env_path = tmp_data_dir / ".env"
        env_path.write_text("EXISTING=old\nTEST_KEY=original\n")

        with patch("local_pigeon.ui.env_utils.get_data_dir", return_value=tmp_data_dir):
            save_env_var("TEST_KEY", "updated")

        content = env_path.read_text()
        assert content.count("TEST_KEY") == 1
        assert "TEST_KEY=updated" in content
        assert "EXISTING=old" in content

    def test_preserves_comments(self, tmp_data_dir):
        """Should not clobber comment lines."""
        env_path = tmp_data_dir / ".env"
        env_path.write_text("# Header comment\nKEY=val\n")

        with patch("local_pigeon.ui.env_utils.get_data_dir", return_value=tmp_data_dir):
            save_env_var("NEW", "new_val")

        content = env_path.read_text()
        assert "KEY=val" in content
        assert "NEW=new_val" in content

    def test_sets_os_environ(self, tmp_data_dir):
        """Should set the variable in the current process."""
        import os

        with patch("local_pigeon.ui.env_utils.get_data_dir", return_value=tmp_data_dir):
            save_env_var("LP_TEST_UNIQUE_KEY", "hello")

        assert os.environ.get("LP_TEST_UNIQUE_KEY") == "hello"
        # Clean up
        os.environ.pop("LP_TEST_UNIQUE_KEY", None)
