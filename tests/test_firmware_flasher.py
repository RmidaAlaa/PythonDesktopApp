"""Tests for firmware flashing functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from src.core.firmware_flasher import FirmwareFlasher, BoardType
from src.core.device_detector import Device

class TestFirmwareFlasher:
    """Test cases for FirmwareFlasher."""
    
    @pytest.fixture
    def flasher(self):
        return FirmwareFlasher()
        
    @pytest.fixture
    def mock_device(self):
        device = MagicMock(spec=Device)
        device.board_type = BoardType.STM32
        device.port = "COM3"
        return device

    def test_guess_board_type_stm32_by_vid(self, flasher):
        """Test guessing board type by VID."""
        device = MagicMock(spec=Device)
        device.vid = "0x0483"
        device.description = "Generic Device"
        
        path = Path("firmware.bin")
        board_type = flasher._guess_board_type(device, path)
        assert board_type == BoardType.STM32

    def test_guess_board_type_stm32_by_name(self, flasher):
        """Test guessing board type by filename."""
        device = MagicMock(spec=Device)
        device.vid = "0x1234" # Non-STM VID
        
        path = Path("project_stm32_v1.bin")
        board_type = flasher._guess_board_type(device, path)
        assert board_type == BoardType.STM32

    @patch('src.core.firmware_flasher.Path.exists')
    def test_get_firmware_file_local(self, mock_exists, flasher):
        """Test getting local firmware file."""
        mock_exists.return_value = True
        
        path = flasher._get_firmware_file("C:/firmware.bin", None)
        assert path == Path("C:/firmware.bin")
        
    def test_get_firmware_file_invalid_ext(self, flasher):
        """Test getting file with invalid extension."""
        with patch('pathlib.Path.exists', return_value=True):
            path = flasher._get_firmware_file("C:/firmware.txt", None)
            assert path is None

    @patch('src.core.firmware_flasher.FirmwareFlasher._flash_stm32')
    @patch('src.core.firmware_flasher.FirmwareFlasher._get_firmware_file')
    def test_flash_firmware_success(self, mock_get_file, mock_flash_stm32, flasher, mock_device):
        """Test successful flashing flow."""
        mock_get_file.return_value = Path("firmware.bin")
        mock_flash_stm32.return_value = True
        
        # Mock Path.exists to return True for the firmware path
        with patch('pathlib.Path.exists', return_value=True):
            result = flasher.flash_firmware(mock_device, "firmware.bin")
            
        assert result is True
        mock_flash_stm32.assert_called_once()

    @patch('src.core.firmware_flasher.FirmwareFlasher._get_firmware_file')
    def test_flash_firmware_invalid_source(self, mock_get_file, flasher, mock_device):
        """Test flashing with invalid source."""
        mock_get_file.return_value = None
        
        result = flasher.flash_firmware(mock_device, "invalid.txt")
        assert result is False
