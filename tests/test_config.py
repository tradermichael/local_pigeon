"""
Tests for configuration loading and settings.
"""

import pytest
from local_pigeon.config import (
    Settings,
    OllamaSettings,
    PaymentSettings,
    PaymentApprovalSettings,
    get_settings,
)


class TestOllamaSettings:
    """Test Ollama settings have required attributes."""
    
    def test_has_host(self):
        settings = OllamaSettings()
        assert hasattr(settings, 'host')
        assert isinstance(settings.host, str)
    
    def test_has_model(self):
        settings = OllamaSettings()
        assert hasattr(settings, 'model')
        assert isinstance(settings.model, str)
    
    def test_has_temperature(self):
        settings = OllamaSettings()
        assert hasattr(settings, 'temperature')
        assert isinstance(settings.temperature, float)
    
    def test_has_max_tokens(self):
        settings = OllamaSettings()
        assert hasattr(settings, 'max_tokens')
        assert isinstance(settings.max_tokens, int)
    
    def test_has_context_length(self):
        settings = OllamaSettings()
        assert hasattr(settings, 'context_length')
        assert isinstance(settings.context_length, int)


class TestPaymentSettings:
    """Test payment settings structure."""
    
    def test_has_approval_nested(self):
        settings = PaymentSettings()
        assert hasattr(settings, 'approval')
        assert isinstance(settings.approval, PaymentApprovalSettings)
    
    def test_approval_has_threshold(self):
        settings = PaymentSettings()
        assert hasattr(settings.approval, 'threshold')
        assert isinstance(settings.approval.threshold, float)
    
    def test_approval_has_require_approval(self):
        settings = PaymentSettings()
        assert hasattr(settings.approval, 'require_approval')
        assert isinstance(settings.approval.require_approval, bool)
    
    def test_approval_has_daily_limit(self):
        settings = PaymentSettings()
        assert hasattr(settings.approval, 'daily_limit')
        assert isinstance(settings.approval.daily_limit, float)


class TestMainSettings:
    """Test main Settings class."""
    
    def test_can_create_settings(self):
        settings = Settings()
        assert settings is not None
    
    def test_has_ollama(self):
        settings = Settings()
        assert hasattr(settings, 'ollama')
        assert isinstance(settings.ollama, OllamaSettings)
    
    def test_has_payments(self):
        settings = Settings()
        assert hasattr(settings, 'payments')
        assert isinstance(settings.payments, PaymentSettings)
    
    def test_has_ui(self):
        settings = Settings()
        assert hasattr(settings, 'ui')
    
    def test_can_load_settings(self):
        settings = Settings.load()
        assert settings is not None
