"""
Tests for the Gradio web UI.
"""

import pytest
from local_pigeon.config import Settings


class TestUICreation:
    """Test that the UI can be created without errors."""
    
    def test_can_import_create_app(self):
        """Test that create_app can be imported."""
        from local_pigeon.ui.app import create_app
        assert create_app is not None
    
    def test_can_import_launch_ui(self):
        """Test that launch_ui can be imported."""
        from local_pigeon.ui.app import launch_ui
        assert launch_ui is not None
    
    def test_create_app_with_default_settings(self):
        """Test that create_app works with default settings."""
        from local_pigeon.ui.app import create_app
        
        settings = Settings()
        app = create_app(settings)
        assert app is not None
    
    def test_create_app_with_loaded_settings(self):
        """Test that create_app works with loaded settings."""
        from local_pigeon.ui.app import create_app
        
        settings = Settings.load()
        app = create_app(settings)
        assert app is not None
    
    def test_ui_settings_access(self):
        """Test that UI can access all required settings."""
        settings = Settings()
        
        # These are accessed in the UI code
        assert settings.ollama.model is not None
        assert settings.ollama.temperature is not None
        assert settings.ollama.max_tokens is not None
        assert settings.ollama.host is not None
        
        assert settings.payments.approval.threshold is not None
        assert settings.payments.approval.require_approval is not None
        
        assert settings.ui.host is not None
        assert settings.ui.port is not None
