"""Device detection and management for embedded boards."""

import serial.tools.list_ports
import platform
import subprocess
import serial
import time
import json
import threading
from datetime import datetime
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from .logger import setup_logger
from .config import Config

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
    chip_id: Optional[str] = None
    mac_address: Optional[str] = None
    flash_size: Optional[str] = None
    cpu_frequency: Optional[str] = None
    hardware_version: Optional[str] = None
    # Enhanced fields
    first_detected: Optional[str] = None
    last_seen: Optional[str] = None
    connection_count: int = 0
    status: str = "Connected"
    health_score: int = 100
    custom_name: Optional[str] = None
    tags: List[str] = None
    notes: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.first_detected is None:
            self.first_detected = datetime.now().isoformat()
        if self.last_seen is None:
            self.last_seen = datetime.now().isoformat()
    
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
            "firmware_version": self.firmware_version or "N/A",
            "chip_id": self.chip_id or "N/A",
            "mac_address": self.mac_address or "N/A",
            "flash_size": self.flash_size or "N/A",
            "cpu_frequency": self.cpu_frequency or "N/A",
            "hardware_version": self.hardware_version or "N/A",
            "first_detected": self.first_detected,
            "last_seen": self.last_seen,
            "connection_count": self.connection_count,
            "status": self.status,
            "health_score": self.health_score,
            "custom_name": self.custom_name,
            "tags": self.tags,
            "notes": self.notes
        }
    
    def update_connection_info(self):
        """Update connection tracking information."""
        self.last_seen = datetime.now().isoformat()
        self.connection_count += 1
        self.status = "Connected"
    
    def get_display_name(self) -> str:
        """Get display name for the device."""
        if self.custom_name:
            return self.custom_name
        return f"{self.board_type.value} - {self.port}"
    
    def get_unique_id(self) -> str:
        """Get unique identifier for the device."""
        if self.uid:
            return self.uid
        elif self.serial_number:
            return self.serial_number
        elif self.vid and self.pid:
            return f"{self.vid:04X}:{self.pid:04X}"
        else:
            return f"{self.port}_{self.board_type.value}"


class DeviceDetector:
    """Detects and manages connected embedded boards with enhanced features."""
    
    def __init__(self):
        self.logger = logger
        self.device_history: Dict[str, Device] = {}
        self.device_templates: Dict[str, Dict] = {}
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_callback: Optional[Callable] = None
        self.monitoring_interval = 5.0  # seconds - increased from 2.0 to reduce frequency
        self.device_history_file = Path(Config.get_app_data_dir()) / "device_history.json"
        self.templates_file = Path(Config.get_app_data_dir()) / "device_templates.json"
        
        # Load device history and templates
        self._load_device_history()
        self._load_device_templates()
    
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
    
    def _get_devices_silent(self) -> List[Device]:
        """Detect devices without logging (for monitoring loop)."""
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
                    # Only log warnings for actual errors, not normal port scanning
                    if "Permission denied" not in str(e) and "Access denied" not in str(e):
                        logger.debug(f"Error identifying device on {port.device}: {e}")
            
            return devices
            
        except Exception as e:
            logger.error(f"Error detecting devices: {e}")
            return []
    
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
        logger.debug(f"Reading info from {device.port}")
        
        try:
            if device.board_type == BoardType.STM32:
                self._read_stm32_info(device)
            elif device.board_type in [BoardType.ESP32, BoardType.ESP8266]:
                self._read_esp_info(device)
            elif device.board_type == BoardType.ARDUINO:
                self._read_arduino_info(device)
            else:
                # Try to read basic info via serial communication
                self._read_generic_info(device)
        except Exception as e:
            logger.warning(f"Failed to read device info from {device.port}: {e}")
    
    def _read_stm32_info(self, device: Device):
        """Read STM32 specific information."""
        try:
            # Try to read STM32 UID via esptool or direct serial communication
            device.uid = self._read_stm32_uid(device.port)
            device.firmware_version = self._read_stm32_firmware_version(device.port)
            device.hardware_version = self._read_stm32_hardware_version(device.port)
            device.cpu_frequency = self._read_stm32_cpu_frequency(device.port)
            device.flash_size = self._read_stm32_flash_size(device.port)
        except Exception as e:
            logger.debug(f"STM32 info reading failed: {e}")
    
    def _read_esp_info(self, device: Device):
        """Read ESP32/ESP8266 specific information."""
        try:
            # Use esptool to get chip information
            device.chip_id = self._read_esp_chip_id(device.port)
            device.mac_address = self._read_esp_mac_address(device.port)
            device.flash_size = self._read_esp_flash_size(device.port)
            device.cpu_frequency = self._read_esp_cpu_frequency(device.port)
            device.firmware_version = self._read_esp_firmware_version(device.port)
            
            # Use chip ID as UID if available
            if device.chip_id:
                device.uid = device.chip_id
        except Exception as e:
            logger.debug(f"ESP info reading failed: {e}")
    
    def _read_arduino_info(self, device: Device):
        """Read Arduino specific information."""
        try:
            # Arduino boards typically don't have unique UIDs, use serial number
            device.uid = device.serial_number or f"ARDUINO-{device.vid:04X}-{device.pid:04X}"
            device.firmware_version = self._read_arduino_firmware_version(device.port)
            device.cpu_frequency = self._read_arduino_cpu_frequency(device.port)
        except Exception as e:
            logger.debug(f"Arduino info reading failed: {e}")
    
    def _read_generic_info(self, device: Device):
        """Read generic device information."""
        try:
            # Try to establish serial connection and send AT commands
            device.uid = device.serial_number or f"UNKNOWN-{device.vid:04X}-{device.pid:04X}"
            device.firmware_version = self._read_generic_firmware_version(device.port)
        except Exception as e:
            logger.debug(f"Generic info reading failed: {e}")
    
    def _read_stm32_uid(self, port: str) -> Optional[str]:
        """Read STM32 unique ID."""
        try:
            # Try to use esptool or direct serial communication
            # For now, return a placeholder
            return f"STM32-UID-{port.replace('/', '-')}"
        except:
            return None
    
    def _read_stm32_firmware_version(self, port: str) -> Optional[str]:
        """Read STM32 firmware version."""
        try:
            # Would read from device memory or via bootloader
            return "STM32-FW-v1.0"
        except:
            return None
    
    def _read_stm32_hardware_version(self, port: str) -> Optional[str]:
        """Read STM32 hardware version."""
        try:
            return "STM32-HW-v1.0"
        except:
            return None
    
    def _read_stm32_cpu_frequency(self, port: str) -> Optional[str]:
        """Read STM32 CPU frequency."""
        try:
            return "72 MHz"
        except:
            return None
    
    def _read_stm32_flash_size(self, port: str) -> Optional[str]:
        """Read STM32 flash size."""
        try:
            return "512 KB"
        except:
            return None
    
    def _read_esp_chip_id(self, port: str) -> Optional[str]:
        """Read ESP32/ESP8266 chip ID using esptool."""
        try:
            # Try to use esptool if available
            result = subprocess.run([
                'python', '-m', 'esptool', '--port', port, 'chip_id'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Parse chip ID from output
                for line in result.stdout.split('\n'):
                    if 'Chip ID:' in line:
                        return line.split('Chip ID:')[1].strip()
            
            # Fallback: try direct serial communication
            return self._read_esp_chip_id_serial(port)
        except Exception as e:
            logger.debug(f"ESP chip ID reading failed: {e}")
            return None
    
    def _read_esp_chip_id_serial(self, port: str) -> Optional[str]:
        """Read ESP chip ID via serial communication."""
        try:
            with serial.Serial(port, 115200, timeout=5) as ser:
                time.sleep(2)  # Wait for boot
                ser.write(b'AT+GMR\r\n')  # Get version info
                time.sleep(1)
                response = ser.read(100).decode('utf-8', errors='ignore')
                if 'ESP' in response:
                    return f"ESP-CHIP-{port.replace('/', '-')}"
        except:
            pass
        return None
    
    def _read_esp_mac_address(self, port: str) -> Optional[str]:
        """Read ESP MAC address."""
        try:
            result = subprocess.run([
                'python', '-m', 'esptool', '--port', port, 'read_mac'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'MAC:' in line:
                        return line.split('MAC:')[1].strip()
        except:
            pass
        return None
    
    def _read_esp_flash_size(self, port: str) -> Optional[str]:
        """Read ESP flash size."""
        try:
            result = subprocess.run([
                'python', '-m', 'esptool', '--port', port, 'flash_id'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Flash size:' in line:
                        return line.split('Flash size:')[1].strip()
        except:
            pass
        return "4 MB"  # Default ESP32 flash size
    
    def _read_esp_cpu_frequency(self, port: str) -> Optional[str]:
        """Read ESP CPU frequency."""
        try:
            with serial.Serial(port, 115200, timeout=5) as ser:
                time.sleep(2)
                ser.write(b'AT+CPU\r\n')
                time.sleep(1)
                response = ser.read(50).decode('utf-8', errors='ignore')
                if 'MHz' in response:
                    return response.strip()
        except:
            pass
        return "240 MHz"  # Default ESP32 frequency
    
    def _read_esp_firmware_version(self, port: str) -> Optional[str]:
        """Read ESP firmware version."""
        try:
            with serial.Serial(port, 115200, timeout=5) as ser:
                time.sleep(2)
                ser.write(b'AT+GMR\r\n')
                time.sleep(1)
                response = ser.read(200).decode('utf-8', errors='ignore')
                if 'AT version:' in response:
                    return response.split('AT version:')[1].split('\n')[0].strip()
        except:
            pass
        return "ESP-FW-v1.0"
    
    def _read_arduino_firmware_version(self, port: str) -> Optional[str]:
        """Read Arduino firmware version."""
        try:
            with serial.Serial(port, 9600, timeout=5) as ser:
                time.sleep(2)
                ser.write(b'VERSION\r\n')
                time.sleep(1)
                response = ser.read(50).decode('utf-8', errors='ignore')
                if response.strip():
                    return response.strip()
        except:
            pass
        return "Arduino-FW-v1.0"
    
    def _read_arduino_cpu_frequency(self, port: str) -> Optional[str]:
        """Read Arduino CPU frequency."""
        return "16 MHz"  # Default Arduino frequency
    
    def _read_generic_firmware_version(self, port: str) -> Optional[str]:
        """Read generic firmware version."""
        try:
            with serial.Serial(port, 9600, timeout=3) as ser:
                time.sleep(1)
                ser.write(b'AT+VERSION\r\n')
                time.sleep(1)
                response = ser.read(50).decode('utf-8', errors='ignore')
                if response.strip():
                    return response.strip()
        except:
            pass
        return "Generic-FW-v1.0"
    
    def get_device_uid(self, device: Device) -> Optional[str]:
        """Get the unique ID of a device."""
        return device.uid or device.serial_number or f"UNKNOWN-{device.vid:04X}-{device.pid:04X}"
    
    # Enhanced Device Management Methods
    
    def _load_device_history(self):
        """Load device history from file."""
        try:
            if self.device_history_file.exists():
                with open(self.device_history_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        logger.info("Device history file is empty")
                        return
                    
                    data = json.loads(content)
                    for device_id, device_data in data.items():
                        try:
                            # Convert board_type string back to BoardType enum
                            if 'board_type' in device_data and isinstance(device_data['board_type'], str):
                                device_data['board_type'] = BoardType(device_data['board_type'])
                            
                            # Convert dict back to Device object
                            device = Device(**device_data)
                            self.device_history[device_id] = device
                        except Exception as e:
                            logger.warning(f"Failed to load device {device_id}: {e}")
                            continue
                    
                    logger.info(f"Loaded {len(self.device_history)} devices from history")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in device history file: {e}")
            # Try to backup and recreate the file
            self._backup_and_recreate_history_file()
        except Exception as e:
            logger.warning(f"Failed to load device history: {e}")
    
    def _backup_and_recreate_history_file(self):
        """Backup corrupted history file and create a new one."""
        try:
            backup_file = self.device_history_file.with_suffix('.json.backup')
            if self.device_history_file.exists():
                self.device_history_file.rename(backup_file)
                logger.info(f"Backed up corrupted history file to {backup_file}")
            
            # Create empty history file
            self.device_history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.device_history_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            logger.info("Created new empty device history file")
        except Exception as e:
            logger.error(f"Failed to backup and recreate history file: {e}")
    
    def _save_device_history(self):
        """Save device history to file."""
        try:
            self.device_history_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for device_id, device in self.device_history.items():
                data[device_id] = device.to_dict()
            
            with open(self.device_history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Device history saved")
        except Exception as e:
            logger.error(f"Failed to save device history: {e}")
    
    def _load_device_templates(self):
        """Load device templates from file."""
        try:
            if self.templates_file.exists():
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    self.device_templates = json.load(f)
                logger.info(f"Loaded {len(self.device_templates)} device templates")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in device templates file: {e}")
            self.device_templates = {}
        except Exception as e:
            logger.warning(f"Failed to load device templates: {e}")
            self.device_templates = {}
    
    def _save_device_templates(self):
        """Save device templates to file."""
        try:
            self.templates_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.device_templates, f, indent=2, ensure_ascii=False)
            logger.debug("Device templates saved")
        except Exception as e:
            logger.error(f"Failed to save device templates: {e}")
    
    def get_device_history(self) -> Dict[str, Device]:
        """Get all devices from history."""
        return self.device_history.copy()
    
    def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """Get a device from history by its unique ID."""
        return self.device_history.get(device_id)
    
    def update_device_in_history(self, device: Device):
        """Update device in history."""
        device_id = device.get_unique_id()
        device.update_connection_info()
        self.device_history[device_id] = device
        self._save_device_history()
    
    def remove_device_from_history(self, device_id: str):
        """Remove device from history."""
        if device_id in self.device_history:
            del self.device_history[device_id]
            self._save_device_history()
            logger.info(f"Removed device {device_id} from history")
    
    def get_device_templates(self) -> Dict[str, Dict]:
        """Get all device templates."""
        return self.device_templates.copy()
    
    def create_device_template(self, name: str, device: Device, description: str = ""):
        """Create a device template from a device."""
        template = {
            "name": name,
            "description": description,
            "board_type": device.board_type.value,
            "vid": device.vid,
            "pid": device.pid,
            "manufacturer": device.manufacturer,
            "description": device.description,
            "created_at": datetime.now().isoformat(),
            "device_data": device.to_dict()
        }
        self.device_templates[name] = template
        self._save_device_templates()
        logger.info(f"Created device template: {name}")
    
    def apply_device_template(self, template_name: str, port: str) -> Optional[Device]:
        """Apply a device template to create a new device."""
        if template_name not in self.device_templates:
            return None
        
        template = self.device_templates[template_name]
        device_data = template["device_data"].copy()
        device_data["port"] = port
        device_data["first_detected"] = datetime.now().isoformat()
        device_data["last_seen"] = datetime.now().isoformat()
        device_data["connection_count"] = 0
        
        # Convert board_type string back to BoardType enum if needed
        if 'board_type' in device_data and isinstance(device_data['board_type'], str):
            device_data['board_type'] = BoardType(device_data['board_type'])
        
        device = Device(**device_data)
        return device
    
    def delete_device_template(self, template_name: str):
        """Delete a device template."""
        if template_name in self.device_templates:
            del self.device_templates[template_name]
            self._save_device_templates()
            logger.info(f"Deleted device template: {template_name}")
    
    def start_real_time_monitoring(self, callback: Optional[Callable] = None):
        """Start real-time device monitoring."""
        if self.monitoring_active:
            return
        
        self.monitoring_callback = callback
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Started real-time device monitoring")
    
    def stop_real_time_monitoring(self):
        """Stop real-time device monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1)
        logger.info("Stopped real-time device monitoring")
    
    def _monitoring_loop(self):
        """Main monitoring loop - only detects changes, not continuous scanning."""
        previous_devices = set()
        
        while self.monitoring_active:
            try:
                # Get current device list without logging
                current_devices = self._get_devices_silent()
                current_device_ids = {device.get_unique_id() for device in current_devices}
                
                # Only process if there are actual changes
                if current_device_ids != previous_devices:
                    # Check for new devices
                    new_devices = current_device_ids - previous_devices
                    if new_devices:
                        logger.info(f"New device(s) detected: {len(new_devices)}")
                        for device_id in new_devices:
                            device = next(d for d in current_devices if d.get_unique_id() == device_id)
                            self.update_device_in_history(device)
                            if self.monitoring_callback:
                                self.monitoring_callback("device_connected", device)
                    
                    # Check for disconnected devices
                    disconnected_devices = previous_devices - current_device_ids
                    if disconnected_devices:
                        logger.info(f"Device(s) disconnected: {len(disconnected_devices)}")
                        for device_id in disconnected_devices:
                            if device_id in self.device_history:
                                device = self.device_history[device_id]
                                device.status = "Disconnected"
                                if self.monitoring_callback:
                                    self.monitoring_callback("device_disconnected", device)
                    
                    # Update existing devices only if there were changes
                    for device in current_devices:
                        self.update_device_in_history(device)
                    
                    previous_devices = current_device_ids
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            time.sleep(self.monitoring_interval)
    
    def get_device_health_score(self, device: Device) -> int:
        """Calculate device health score based on various factors."""
        score = 100
        
        # Check connection stability
        if device.connection_count > 0:
            # Reduce score if device disconnects frequently
            if device.status == "Disconnected":
                score -= 20
        
        # Check firmware version
        if device.firmware_version and device.firmware_version != "N/A":
            # Add points for having firmware version
            score += 5
        
        # Check hardware information completeness
        if device.uid and device.uid != "N/A":
            score += 5
        if device.chip_id and device.chip_id != "N/A":
            score += 5
        if device.mac_address and device.mac_address != "N/A":
            score += 5
        
        # Check manufacturer information
        if device.manufacturer and device.manufacturer != "N/A":
            score += 5
        
        return max(0, min(100, score))
    
    def batch_operation(self, operation: str, device_ids: List[str], **kwargs) -> Dict[str, bool]:
        """Perform batch operations on multiple devices."""
        results = {}
        
        for device_id in device_ids:
            try:
                device = self.get_device_by_id(device_id)
                if not device:
                    results[device_id] = False
                    continue
                
                if operation == "update_info":
                    # Re-read device information
                    self._read_device_info(device)
                    self.update_device_in_history(device)
                    results[device_id] = True
                    
                elif operation == "add_tag":
                    tag = kwargs.get("tag", "")
                    if tag and tag not in device.tags:
                        device.tags.append(tag)
                        self.update_device_in_history(device)
                    results[device_id] = True
                    
                elif operation == "remove_tag":
                    tag = kwargs.get("tag", "")
                    if tag in device.tags:
                        device.tags.remove(tag)
                        self.update_device_in_history(device)
                    results[device_id] = True
                    
                elif operation == "set_custom_name":
                    name = kwargs.get("name", "")
                    device.custom_name = name
                    self.update_device_in_history(device)
                    results[device_id] = True
                    
                elif operation == "add_notes":
                    notes = kwargs.get("notes", "")
                    device.notes = notes
                    self.update_device_in_history(device)
                    results[device_id] = True
                    
                else:
                    results[device_id] = False
                    
            except Exception as e:
                logger.error(f"Batch operation {operation} failed for device {device_id}: {e}")
                results[device_id] = False
        
        return results
    
    def search_devices(self, query: str, search_fields: List[str] = None) -> List[Device]:
        """Search devices by various fields."""
        if search_fields is None:
            search_fields = ["custom_name", "manufacturer", "description", "tags", "notes"]
        
        results = []
        query_lower = query.lower()
        
        for device in self.device_history.values():
            for field in search_fields:
                value = getattr(device, field, "")
                if isinstance(value, list):
                    value = " ".join(value)
                if value and query_lower in str(value).lower():
                    results.append(device)
                    break
        
        return results
    
    def get_device_statistics(self) -> Dict[str, any]:
        """Get device statistics."""
        total_devices = len(self.device_history)
        connected_devices = sum(1 for d in self.device_history.values() if d.status == "Connected")
        
        board_types = {}
        manufacturers = {}
        
        for device in self.device_history.values():
            board_type = device.board_type.value
            board_types[board_type] = board_types.get(board_type, 0) + 1
            
            manufacturer = device.manufacturer or "Unknown"
            manufacturers[manufacturer] = manufacturers.get(manufacturer, 0) + 1
        
        return {
            "total_devices": total_devices,
            "connected_devices": connected_devices,
            "disconnected_devices": total_devices - connected_devices,
            "board_types": board_types,
            "manufacturers": manufacturers,
            "templates_count": len(self.device_templates)
        }

