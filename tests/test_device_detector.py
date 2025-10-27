"""Tests for device detection functionality."""

import pytest
from unittest.mock import Mock, patch
from src.core.device_detector import DeviceDetector, BoardType, Device


class TestDeviceDetector:
    """Test cases for DeviceDetector."""
    
    def test_init(self):
        """Test DeviceDetector initialization."""
        detector = DeviceDetector()
        assert detector is not None
        assert detector.logger is not None
    
    @patch('serial.tools.list_ports.comports')
    def test_detect_devices_empty(self, mock_comports):
        """Test device detection with no devices."""
        mock_comports.return_value = []
        detector = DeviceDetector()
        devices = detector.detect_devices()
        assert len(devices) == 0
    
    @patch('serial.tools.list_ports.comports')
    def test_detect_devices_stm32(self, mock_comports):
        """Test device detection with STM32 board."""
        mock_port = Mock()
        mock_port.device = "COM3"
        mock_port.vid = 0x0483
        mock_port.pid = 0x5740
        mock_port.serial_number = "12345"
        mock_port.manufacturer = "STMicroelectronics"
        mock_port.description = "STM32 Virtual COM Port"
        
        mock_comports.return_value = [mock_port]
        
        detector = DeviceDetector()
        devices = detector.detect_devices()
        
        assert len(devices) == 1
        assert devices[0].board_type == BoardType.STM32
        assert devices[0].port == "COM3"
    
    def test_device_to_dict(self):
        """Test Device to_dict conversion."""
        device = Device(
            port="COM3",
            board_type=BoardType.STM32,
            vid=0x0483,
            pid=0x5740
        )
        device_dict = device.to_dict()
        
        assert device_dict['port'] == "COM3"
        assert device_dict['board_type'] == "STM32"
        assert device_dict['vid'] == "0x0483"
        assert device_dict['pid'] == "0x5740"

