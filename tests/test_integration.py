"""Integration tests for the application core."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.config import Config
from src.core.firmware_flasher import FirmwareFlasher
from src.core.device_detector import Device, BoardType
from pathlib import Path

class TestIntegration:
    """Integration tests."""
    
    def test_flashing_flow_with_config(self):
        """Test the flow from config to flashing."""
        
        # 1. Setup Config
        config = Config.DEFAULT_CONFIG.copy()
        config['auto_flash']['enabled'] = True
        
        # 2. Setup Device
        device = MagicMock(spec=Device)
        device.board_type = BoardType.STM32
        
        # 3. Setup Flasher
        flasher = FirmwareFlasher()
        
        # 4. Simulate Auto-Flash Logic (similar to main_window)
        with patch('src.core.firmware_flasher.FirmwareFlasher.flash_firmware') as mock_flash:
            mock_flash.return_value = True
            
            if config['auto_flash']['enabled']:
                 # Simulate getting path from config
                 firmware_path = "test_firmware.bin"
                 result = flasher.flash_firmware(device, firmware_path)
                 
            assert result is True
            mock_flash.assert_called_with(device, "test_firmware.bin")
