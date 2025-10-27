"""Device detection and management for embedded boards."""

import serial.tools.list_ports
import platform
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

from .logger import setup_logger

logger = setup_logger("DeviceDetector")


class BoardType(Enum):
    """Supported board types."""
    STM32 = "STM32"
    ESP32 = "ESP32"
    ESP8266 = "ESP8266"
    ARDUINO = "Arduino"
    UNKNOWN = "Unknown"


@dataclass
class Device:
    """Represents a detected device."""
    port: str
    board_type: BoardType
    vid: Optional[int] = None
    pid: Optional[int] = None
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    uid: Optional[str] = None
    firmware_version: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "port": self.port,
            "board_type": self.board_type.value,
            "vid": f"0x{self.vid:04X}" if self.vid else None,
            "pid": f"0x{self.pid:04X}" if self.pid else None,
            "serial_number": self.serial_number or "N/A",
            "manufacturer": self.manufacturer or "N/A",
            "description": self.description or "N/A",
            "uid": self.uid or "N/A",
            "firmware_version": self.firmware_version or "N/A"
        }


class DeviceDetector:
    """Detects and manages connected embedded boards."""
    
    # VID:PID mappings for known boards
    BOARD_VIDPIDS = {
        # STM32 boards
        (0x0483, 0x5740): BoardType.STM32,  # STM32 Virtual COM Port
        (0x0483, 0x3748): BoardType.STM32,  # STM32 in DFU mode
        
        # ESP32
        (0x10C4, 0xEA60): BoardType.ESP32,  # CP210x UART Bridge
        (0x303A, 0x0001): BoardType.ESP32,  # ESP32-DevKitC
        (0x303A, 0x1001): BoardType.ESP32,  # ESP32-WROOM-DA Module
        
        # ESP8266
        (0x10C4, 0xEA60): BoardType.ESP8266,  # NodeMCU
        
        # Arduino
        (0x2341, 0x0043): BoardType.ARDUINO,  # Arduino Uno
        (0x2341, 0x0010): BoardType.ARDUINO,  # Arduino Mega
        (0x2A03, 0x0043): BoardType.ARDUINO,  # Arduino Uno (clone)
    }
    
    def __init__(self):
        self.logger = logger
    
    def detect_devices(self) -> List[Device]:
        """Detect all connected devices."""
        devices = []
        
        try:
            # Get all serial ports
            ports = serial.tools.list_ports.comports()
            
            for port in ports:
                try:
                    device = self._identify_device(port)
                    if device:
                        devices.append(device)
                except Exception as e:
                    logger.warning(f"Error identifying device on {port.device}: {e}")
            
            logger.info(f"Detected {len(devices)} device(s)")
            return devices
            
        except Exception as e:
            logger.error(f"Error detecting devices: {e}")
            return []
    
    def _identify_device(self, port) -> Optional[Device]:
        """Identify a single device."""
        vid = port.vid
        pid = port.pid
        
        # Try to determine board type from VID:PID
        board_type = self.BOARD_VIDPIDS.get((vid, pid), BoardType.UNKNOWN)
        
        # Create device
        device = Device(
            port=port.device,
            board_type=board_type,
            vid=vid,
            pid=pid,
            serial_number=port.serial_number,
            manufacturer=port.manufacturer,
            description=port.description
        )
        
        # Try to read additional info (UID, firmware version, etc.)
        self._read_device_info(device)
        
        return device
    
    def _read_device_info(self, device: Device):
        """Read additional information from the device."""
        # This would involve sending commands to the device based on its type
        # For now, we'll just log that we would read the info
        logger.debug(f"Reading info from {device.port}")
        
        if device.board_type == BoardType.STM32:
            # Would use STM32 CLI or direct memory read
            # device.uid = self._read_stm32_uid(device.port)
            pass
        elif device.board_type in [BoardType.ESP32, BoardType.ESP8266]:
            # Would use esptool to get chip ID
            # device.uid = self._read_esp_chipid(device.port)
            pass
        elif device.board_type == BoardType.ARDUINO:
            # Would read via USB descriptor or avrdude
            pass
    
    def get_device_uid(self, device: Device) -> Optional[str]:
        """Get the unique ID of a device."""
        # This would implement actual UID reading based on board type
        return device.serial_number or f"UNKNOWN-{device.vid:04X}-{device.pid:04X}"

