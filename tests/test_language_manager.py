"""Tests for language management."""

import pytest
from unittest.mock import Mock, patch
from PySide6.QtCore import QCoreApplication
import sys
from src.core.language_manager import LanguageManager, LanguageType

class TestLanguageManager:
    """Test cases for LanguageManager."""
    
    @pytest.fixture(scope="class")
    def qapp(self):
        """Create QCoreApplication instance."""
        app = QCoreApplication.instance()
        if app is None:
            app = QCoreApplication(sys.argv)
        yield app
    
    @patch('src.core.language_manager.LanguageManager._load_saved_language')
    def test_init(self, mock_load, qapp):
        """Test initialization."""
        manager = LanguageManager()
        assert manager.current_language == LanguageType.ENGLISH
        assert "app_title" in manager.translations['en']

    @patch('src.core.language_manager.LanguageManager._load_saved_language')
    def test_translations_structure(self, mock_load, qapp):
        """Test translation dictionary structure."""
        manager = LanguageManager()
        
        assert 'en' in manager.translations
        assert manager.translations['en']['settings'] == "Settings"
