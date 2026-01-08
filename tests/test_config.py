"""Tests for configuration management."""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path
from src.core.config import Config

class TestConfig:
    """Test cases for Config."""
    
    def test_default_config_values(self):
        """Test default configuration values."""
        assert Config.DEFAULT_CONFIG['version'] == "1.0.0"
        assert Config.DEFAULT_CONFIG['admin_password'] == "AWG"
        assert Config.DEFAULT_CONFIG['smtp']['port'] == 587
        
    @patch('src.core.config.Config.APPDATA_DIR')
    @patch('src.core.config.Config.TOOLS_DIR')
    @patch('src.core.config.Config.LOGS_DIR')
    def test_ensure_directories(self, mock_logs, mock_tools, mock_appdata):
        """Test directory creation."""
        Config.ensure_directories()
        
        mock_appdata.mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_tools.mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_logs.mkdir.assert_called_with(parents=True, exist_ok=True)
        
    @patch('builtins.open', new_callable=mock_open, read_data='{"version": "2.0.0"}')
    @patch('src.core.config.Config.CONFIG_FILE')
    def test_load_config_existing(self, mock_config_file, mock_file):
        """Test loading existing configuration."""
        mock_config_file.exists.return_value = True
        
        config = Config.load_config()
        
        assert config['version'] == "2.0.0"
        # Should still have defaults for missing keys
        assert config['admin_password'] == "AWG"
        
    @patch('src.core.config.Config.CONFIG_FILE')
    def test_load_config_missing(self, mock_config_file):
        """Test loading when config file doesn't exist."""
        mock_config_file.exists.return_value = False
        
        config = Config.load_config()
        
        assert config == Config.DEFAULT_CONFIG

    @patch('src.core.config.platform.system')
    @patch('shutil.which')
    @patch('src.core.config.Config.get_tool_path')
    def test_get_tool_executable(self, mock_get_path, mock_which, mock_system):
        """Test tool executable resolution."""
        # Setup mocks
        mock_tool_dir = MagicMock()
        mock_get_path.return_value = mock_tool_dir
        
        # Case 1: Exists in TOOLS_DIR
        mock_exe_path = MagicMock()
        mock_exe_path.exists.return_value = True
        mock_tool_dir.__truediv__.return_value = mock_exe_path
        
        result = Config.get_tool_executable("test_tool", "test.exe")
        assert result == str(mock_exe_path)
        
        # Case 2: Exists in System PATH
        mock_exe_path.exists.return_value = False
        mock_which.return_value = "C:\\System\\test.exe"
        
        result = Config.get_tool_executable("test_tool", "test.exe")
        assert result == "C:\\System\\test.exe"
        
        # Case 3: Fallback (Force non-Windows to skip common path check which might find real files)
        mock_which.return_value = None
        mock_system.return_value = "Linux" 
        
        result = Config.get_tool_executable("test_tool", "test.exe")
        assert result == str(mock_exe_path)
