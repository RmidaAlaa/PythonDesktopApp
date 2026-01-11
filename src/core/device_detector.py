"""Device detection and management for embedded boards."""

import serial.tools.list_ports
import platform
import subprocess
import serial
import time
import json
import threading
import sys
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import re

from .logger import setup_logger
from .config import Config

logger = setup_logger("DeviceDetector")


class BoardType(Enum):
    """Supported board types."""
    STM32 = "STM32"
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
    extra_info: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.extra_info is None:
            self.extra_info = {}
        if self.first_detected is None:
            self.first_detected = datetime.now().isoformat()
        if self.last_seen is None:
            self.last_seen = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        def _format_hex(value: Optional[object]) -> Optional[str]:
            """Format value as 0xXXXX safely for int or str inputs."""
            if value is None:
                return None
            try:
                if isinstance(value, int):
                    return f"0x{value:04X}"
                if isinstance(value, str):
                    s = value.strip()
                    if s.startswith("0x") or s.startswith("0X"):
                        v = int(s, 16)
                        return f"0x{v:04X}"
                    # Try decimal then hex fallback
                    try:
                        v = int(s)
                        return f"0x{v:04X}"
                    except ValueError:
                        v = int(s, 16)
                        return f"0x{v:04X}"
            except Exception:
                return str(value)
            return str(value)

        return {
            "port": self.port,
            "board_type": self.board_type.value,
            "vid": _format_hex(self.vid),
            "pid": _format_hex(self.pid),
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
            "notes": self.notes,
            "extra_info": self.extra_info
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
        if self.uid:
            return self.uid
        if self.serial_number:
            return self.serial_number
        try:
            if self.vid is not None and self.pid is not None:
                vid_str = f"{int(self.vid):04X}" if not isinstance(self.vid, str) else (
                    f"{int(self.vid, 16):04X}" if str(self.vid).lower().startswith("0x") else f"{int(self.vid):04X}"
                )
                pid_str = f"{int(self.pid):04X}" if not isinstance(self.pid, str) else (
                    f"{int(self.pid, 16):04X}" if str(self.pid).lower().startswith("0x") else f"{int(self.pid):04X}"
                )
                return f"{vid_str}:{pid_str}"
        except Exception:
            pass
        return f"{self.port}_{self.board_type.value}"


class DeviceDetector:
    """Detects and manages connected embedded boards with enhanced features."""
    
    def __init__(self):
        self.logger = logger
        self.device_history: Dict[str, Device] = {}
        self.device_templates: Dict[str, Dict] = {}
        self.monitoring_active = False
        self._paused = False  # Flag to pause monitoring temporarily
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
        (0x0483, 0x374B): BoardType.STM32,  # ST-LINK/V2.1 (Nucleo/Discovery)
        (0x0483, 0x3752): BoardType.STM32,  # ST-LINK/V2.1
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
            
            # Use ThreadPoolExecutor for parallel scanning
            # This significantly reduces scan time when multiple ports are present or some are unresponsive
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_port = {executor.submit(self._identify_device, port): port for port in ports}
                for future in concurrent.futures.as_completed(future_to_port):
                    port = future_to_port[future]
                    try:
                        device = future.result()
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
        # Normalize VID/PID to integers when possible to avoid formatting errors
        vid = port.vid
        pid = port.pid
        try:
            if isinstance(vid, str):
                vid = int(vid, 16) if vid.lower().startswith("0x") else int(vid)
        except Exception:
            pass
        try:
            if isinstance(pid, str):
                pid = int(pid, 16) if pid.lower().startswith("0x") else int(pid)
        except Exception:
            pass
        
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
            else:
                # Try to read basic info via serial communication
                self._read_generic_info(device)
        except Exception as e:
            logger.warning(f"Failed to read device info from {device.port}: {e}")
        finally:
            try:
                metadata = self._read_serial_metadata(device.port)
                if metadata:
                    self._apply_metadata_to_device(device, metadata)
            except Exception as e:
                logger.debug(f"Metadata enrichment failed for {device.port}: {e}")
    
    def _read_stm32_info(self, device: Device):
        """Read STM32 specific information."""
        try:
            # Optimization: Try to find in history first if we have a serial number
            if device.serial_number:
                for hist_device in self.device_history.values():
                    if hist_device.serial_number == device.serial_number and hist_device.uid and hist_device.uid != "N/A":
                        device.uid = hist_device.uid
                        logger.debug(f"Used cached UID for {device.port}")
                        break
            
            if not device.uid:
                # device.uid = self._read_stm32_uid(device.port)
                pass
            
            if not device.uid:
                logger.debug("Firmware UID read failed, trying bootloader method")
                # device.uid = self._read_stm32_uid_bootloader(device.port)
                pass

            device.firmware_version = self._read_stm32_firmware_version(device.port)
            device.hardware_version = self._read_stm32_hardware_version(device.port)
            device.cpu_frequency = self._read_stm32_cpu_frequency(device.port)
            device.flash_size = self._read_stm32_flash_size(device.port)
        except Exception as e:
            logger.debug(f"STM32 info reading failed: {e}")
    
    
    def _read_generic_info(self, device: Device):
        """Read generic device information."""
        try:
            # Try to establish serial connection and send AT commands
            try:
                vid_str = f"{int(device.vid):04X}" if not isinstance(device.vid, str) else (
                    f"{int(device.vid, 16):04X}" if device.vid and device.vid.lower().startswith("0x") else f"{int(device.vid):04X}"
                )
                pid_str = f"{int(device.pid):04X}" if not isinstance(device.pid, str) else (
                    f"{int(device.pid, 16):04X}" if device.pid and device.pid.lower().startswith("0x") else f"{int(device.pid):04X}"
                )
                fallback_uid = f"UNKNOWN-{vid_str}-{pid_str}"
            except Exception:
                fallback_uid = f"UNKNOWN-{device.vid}-{device.pid}"
            device.uid = device.serial_number or fallback_uid
            device.firmware_version = self._read_generic_firmware_version(device.port)
        except Exception as e:
            logger.debug(f"Generic info reading failed: {e}")
    
    def read_all_serial_output(self, port: str, timeout: float = 5.0) -> str:
        """
        Read all available output from the serial port for a given duration.
        Useful for capturing boot logs or comprehensive device info.
        """
        output = []
        try:
            # Try different baud rates if not standard
            baud_rate = 115200
            
            with serial.Serial(port, baud_rate, timeout=1.0) as ser:
                ser.reset_input_buffer()
                
                # Send a newline to potentially wake up the CLI/output
                ser.write(b'\r\n')
                
                start_time = time.time()
                while (time.time() - start_time) < timeout:
                    if ser.in_waiting:
                        try:
                            chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                            output.append(chunk)
                        except Exception:
                            pass
                    time.sleep(0.1)
                    
        except Exception as e:
            logger.warning(f"Failed to read serial output from {port}: {e}")
            return f"Error reading serial: {str(e)}"
            
        return "".join(output)

    def _read_stm32_uid(self, port: str) -> Optional[str]:
        """
        Read STM32 unique ID by sending a 'I' command to the running application.
        The device must be running firmware that implements the 'I' command.

        Returns:
            str: 24-character hex string (96-bit UID) or None if reading fails
        """
        try:
            with serial.Serial(port=port, baudrate=115200, timeout=2.0) as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                # Send 'I' command
                ser.write(b'I')
                
                # Read response (expecting multiple lines)
                start_time = time.time()
                buffer = ""
                while time.time() - start_time < 2.0:
                    if ser.in_waiting:
                        chunk = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                        buffer += chunk
                        if "UID:" in buffer:
                            # Wait a bit more for the rest of the line if needed
                            time.sleep(0.1)
                            if ser.in_waiting:
                                buffer += ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                            break
                    time.sleep(0.05)
                
                # Parse UID from buffer
                for line in buffer.splitlines():
                    line = line.strip()
                    if "UID:" in line:
                         # Extract UID part
                         parts = line.split('UID:')
                         if len(parts) > 1:
                             uid_part = parts[1].strip()
                             # Cleanup if there are other chars (take first word)
                             uid = uid_part.split()[0]
                             # Normalize
                             uid = uid.replace('0x', '').replace(':', '').upper()
                             # Valid UID is usually 24 chars (96 bits)
                             if len(uid) >= 24 and all(c in '0123456789ABCDEF' for c in uid):
                                 return uid
                
                logger.debug(f"UID not found in response: {buffer[:100]}...")
                return None
        except serial.SerialException as e:
            logger.debug(f"Serial error reading UID from {port}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error reading UID: {e}")
        return None

    def _read_stm32_uid_bootloader(self, port: str) -> Optional[str]:
        """Fallback method to read UID using bootloader (for devices without custom firmware)."""
        try:
            with serial.Serial(port=port, baudrate=115200, timeout=2.0) as ser:
                ser.write(b'\x7F')
                if ser.read(1) != b'\x79':
                    return None
                ser.write(b'\x11\xEE')
                if ser.read(1) != b'\x79':
                    return None
                addr = 0x1FFF7A10
                addr_bytes = addr.to_bytes(4, 'big')
                checksum = 0
                for b in addr_bytes:
                    checksum ^= b
                ser.write(addr_bytes + bytes([checksum]))
                if ser.read(1) != b'\x79':
                    return None
                ser.write(b'\xBC')
                if ser.read(1) != b'\x79':
                    return None
                response = ser.read(13)
                if len(response) != 13:
                    return None
                checksum = 0
                for b in response[:-1]:
                    checksum ^= b
                if checksum != response[-1]:
                    return None
                return response[:-1].hex().upper()
        except Exception as e:
            logger.debug(f"Bootloader UID read failed: {e}")
            return None

    def _read_stm32_uid_via_cubeprogrammer(self) -> Optional[str]:
        """Read STM32 UID using STM32CubeProgrammer CLI."""
        try:
            candidates = [
                r"C:\\Program Files\\STMicroelectronics\\STM32Cube\\STM32CubeProgrammer\\bin\\STM32_Programmer_CLI.exe",
                r"C:\\Program Files (x86)\\STMicroelectronics\\STM32Cube\\STM32CubeProgrammer\\bin\\STM32_Programmer_CLI.exe",
                "/opt/st/stm32cubeprogrammer/bin/STM32_Programmer_CLI",
                "STM32_Programmer_CLI"
            ]
            cli = None
            for p in candidates:
                try:
                    r = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=4)
                    if r.returncode == 0 or r.stdout or r.stderr:
                        cli = p
                        break
                except Exception:
                    continue

            if cli:
                # Try different connection methods
                connection_args = [
                    ["-c", "port=SWD"],
                    ["-c", "port=JTAG"],
                    ["-c", "port=SWD", "mode=UR"],
                    ["-c", "port=SWD", "mode=HotPlug"]
                ]

                for conn_args in connection_args:
                    try:
                        # First connect
                        connect_cmd = [cli] + conn_args
                        connect_result = subprocess.run(connect_cmd, capture_output=True, text=True, timeout=10)
                        if connect_result.returncode == 0:
                            # Now read UID
                            uid_cmd = connect_cmd + ["-rduid"]
                            uid_result = subprocess.run(uid_cmd, capture_output=True, text=True, timeout=15)
                            if uid_result.returncode == 0:
                                for line in (uid_result.stdout + "\n" + uid_result.stderr).splitlines():
                                    s = line.strip().lower()
                                    if "unique device id" in s or "uid" in s:
                                        uid_part = line.split(":")[-1].strip()
                                        return self._normalize_uid_string(uid_part)
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"STM32CubeProgrammer UID reading failed: {e}")
        return None

    def _read_stm32_uid_via_stlink(self) -> Optional[str]:
        """Read STM32 UID using ST-LINK Utility."""
        try:
            candidates = [
                r"C:\\Program Files (x86)\\STMicroelectronics\\STM32 ST-LINK Utility\\ST-LINK Utility\\ST-LINK_CLI.exe",
                "ST-LINK_CLI"
            ]
            cli = None
            for p in candidates:
                try:
                    r = subprocess.run([p, "-Version"], capture_output=True, text=True, timeout=4)
                    if r.returncode == 0 or "ST-LINK" in (r.stdout + r.stderr):
                        cli = p
                        break
                except Exception:
                    continue

            if cli:
                # ST-LINK CLI command to read UID
                cmd = [cli, "-c", "SWD", "-r32", "0x1FFF7A10", "3"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    output = result.stdout + result.stderr
                    # Parse memory read output
                    lines = output.split('\n')
                    uid_values = []
                    for line in lines:
                        if '0x1FFF7A1' in line and ':' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                value = parts[1].strip().split()[0]
                                uid_values.append(value)

                    if len(uid_values) >= 3:
                        uid_hex = ''.join(v.lstrip('0x').zfill(8) for v in uid_values[:3])
                        return self._normalize_uid_string(uid_hex)

        except Exception as e:
            logger.debug(f"ST-LINK Utility UID reading failed: {e}")
        return None

    def _read_stm32_uid_via_debug_probe(self) -> Optional[str]:
        """Read STM32 UID via generic debug probe."""
        # This would implement direct JTAG/SWD memory access
        # For now, return None as it requires specific probe libraries
        return None

    def _read_stm32_uid_via_serial(self, port: str) -> Optional[str]:
        """Read STM32 UID via serial communication (after flashing UID firmware)."""
        try:
            # Try different baud rates
            baud_rates = [115200, 9600, 57600, 38400]
            for baud in baud_rates:
                try:
                    with serial.Serial(port, baud, timeout=5) as ser:
                        time.sleep(2)  # Wait for device to boot

                        # Send UID request command
                        ser.write(b'GET_UID\r\n')
                        time.sleep(1)
                        data = ser.read(512).decode('utf-8', errors='ignore').strip()

                        if data:
                            uid = self._parse_uid_from_serial_data(data)
                            if uid:
                                return uid

                        # Alternative: just read any available data
                        ser.write(b'\r\n')  # Send enter to trigger output
                        time.sleep(1)
                        data = ser.read(512).decode('utf-8', errors='ignore').strip()

                        if data:
                            uid = self._parse_uid_from_serial_data(data)
                            if uid:
                                return uid

                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Serial UID reading failed: {e}")
        return None

    def _parse_uid_from_serial_data(self, data: str) -> Optional[str]:
        """Parse UID from serial data."""
        if not data:
            return None

        # Clean the data
        parts = data.replace('-', '').replace(':', '').replace(' ', '').replace('\r', '').replace('\n', '')

        # Look for UID patterns in the output
        # STM32 UID is typically 96 bits (24 hex chars) or 3x32-bit values
        for token in [data] + data.split():
            t = token.strip()
            if t.lower().startswith('0x'):
                t = t[2:]

            # Check for 24+ hex characters (96+ bits)
            if len(t) >= 24 and all(c in '0123456789abcdefABCDEF' for c in t[:min(len(t), 32)]):
                return self._normalize_uid_string(t[:24])

        # Look for "UID:" or similar patterns
        if 'uid' in data.lower():
            try:
                uid_match = re.search(r'uid[:\s]*([0-9a-fA-Fx\s\-:]+)', data, re.IGNORECASE)
                if uid_match:
                    uid_str = uid_match.group(1).strip()
                    uid_str = re.sub(r'[^0-9a-fA-F]', '', uid_str)
                    if len(uid_str) >= 24:
                        return self._normalize_uid_string(uid_str[:24])
            except Exception:
                pass

        # Look for multiple hex values that could be UID parts
        hex_values = re.findall(r'0x([0-9a-fA-F]{8})', data, re.IGNORECASE)
        if len(hex_values) >= 3:
            uid_hex = ''.join(hex_values[:3])
            if len(uid_hex) >= 24:
                return self._normalize_uid_string(uid_hex[:24])

        # Fallback: any long hex string
        hex_match = re.search(r'([0-9a-fA-F]{24,})', parts)
        if hex_match:
            return self._normalize_uid_string(hex_match.group(1)[:24])

        return None

    def _read_stm32_uid_via_jlink(self) -> Optional[str]:
        """Read STM32 UID using J-Link Commander."""
        try:
            candidates = [
                r"C:\\Program Files (x86)\\SEGGER\\JLink\\JLink.exe",
                r"C:\\Program Files\\SEGGER\\JLink\\JLink.exe",
                "JLink.exe",
                "JLinkExe"
            ]
            jlink = None
            for p in candidates:
                try:
                    r = subprocess.run([p, "-version"], capture_output=True, text=True, timeout=4)
                    if r.returncode == 0 or "SEGGER" in (r.stdout + r.stderr):
                        jlink = p
                        break
                except Exception:
                    continue

            if jlink:
                # Create J-Link script
                script_content = """
Connect
r
mem32 0x1FFF7A10, 3
q
"""
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.jlink', delete=False) as f:
                    f.write(script_content)
                    script_path = f.name

                try:
                    cmd = [jlink, "-device", "STM32F407VG", "-if", "SWD", "-speed", "4000", "-CommanderScript", script_path]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)

                    output = result.stdout + result.stderr
                    # Parse memory read output
                    lines = output.split('\n')
                    uid_values = []
                    for line in lines:
                        if '1FFF7A1' in line and ':' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                value = parts[1].strip().split()[0]
                                uid_values.append(value)

                    if len(uid_values) >= 3:
                        uid_hex = ''.join(v.lstrip('0x').zfill(8) for v in uid_values[:3])
                        return self._normalize_uid_string(uid_hex)

                finally:
                    import os
                    os.unlink(script_path)

        except Exception as e:
            logger.debug(f"J-Link UID reading failed: {e}")
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
        """Get the unique ID of a device with safe fallbacks."""
        if device.uid:
            return device.uid

        # For STM32 devices, try to read UID if not already done
        if device.board_type == BoardType.STM32 and not device.uid:
            logger.debug(f"Attempting to read UID for STM32 device on {device.port}")
            
            # Method 1: Direct Serial GET_UID
            device.uid = self._read_stm32_uid(device.port)
            if device.uid:
                logger.info(f"Successfully read UID {device.uid} via Direct Serial")
                return device.uid
            
            # Method 2: Bootloader Protocol
            logger.debug("Direct read failed, trying bootloader method...")
            device.uid = self._read_stm32_uid_bootloader(device.port)
            if device.uid:
                logger.info(f"Successfully read UID {device.uid} via Bootloader")
                return device.uid
                
            # Method 3: CubeProgrammer CLI (last resort)
            logger.debug("Bootloader read failed, trying CubeProgrammer...")
            device.uid = self._read_stm32_uid_via_cubeprogrammer()
            if device.uid:
                logger.info(f"Successfully read UID {device.uid} via CubeProgrammer")
                return device.uid

        if device.serial_number:
            return device.serial_number

        def _fmt(val):
            try:
                if val is None:
                    return None
                if isinstance(val, int):
                    return f"{val:04X}"
                s = str(val).strip()
                if s.lower().startswith("0x"):
                    return f"{int(s,16):04X}"
                return f"{int(s):04X}"
            except Exception:
                return str(val) if val is not None else None
        vid = _fmt(device.vid)
        pid = _fmt(device.pid)
        if vid and pid:
            return f"UNKNOWN-{vid}-{pid}"
        return f"{device.port}_{device.board_type.value}"

    def read_stm32_uid_direct(self, port: str) -> Optional[str]:
        """Direct method to read STM32 UID from a specific port."""
        logger.info(f"Reading STM32 UID from port {port}")
        return self._read_stm32_uid(port)
    
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
                            # Convert VID/PID strings like "0x0483" back to integers
                            if 'vid' in device_data and isinstance(device_data['vid'], str):
                                s = device_data['vid'].strip()
                                try:
                                    device_data['vid'] = int(s, 16) if s.lower().startswith('0x') else int(s)
                                except Exception:
                                    device_data['vid'] = None
                            if 'pid' in device_data and isinstance(device_data['pid'], str):
                                s = device_data['pid'].strip()
                                try:
                                    device_data['pid'] = int(s, 16) if s.lower().startswith('0x') else int(s)
                                except Exception:
                                    device_data['pid'] = None
                            
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
    
    def pause_monitoring(self):
        """Pause real-time monitoring temporarily."""
        self._paused = True
        logger.info("Device monitoring paused")

    def resume_monitoring(self):
        """Resume real-time monitoring."""
        self._paused = False
        logger.info("Device monitoring resumed")

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
                if self._paused:
                    time.sleep(1)
                    continue

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

    def _read_serial_metadata(self, port: Optional[str]) -> Dict[str, str]:
        """Read metadata emitted via serial after flashing helper firmware."""
        if not port:
            return {}
        baud_candidates = [115200, 9600]
        for baud in baud_candidates:
            try:
                with serial.Serial(port, baud, timeout=3) as ser:
                    time.sleep(1)
                    raw = ser.read(768).decode("utf-8", errors="ignore").strip()
                    if not raw:
                        continue
                    metadata = self._parse_metadata_blob(raw)
                    if metadata:
                        metadata.setdefault("raw_output", raw)
                        return metadata
            except Exception as e:
                logger.debug(f"Serial metadata read failed on {port} @ {baud}: {e}")
        return {}

    def _parse_metadata_blob(self, raw: str) -> Dict[str, str]:
        """Parse JSON or key-value style metadata from raw serial output."""
        if not raw:
            return {}
        cleaned = raw.replace("\r", "\n")
        # Try JSON payload first
        try:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_blob = cleaned[start:end + 1]
                data = json.loads(json_blob)
                return {
                    str(k).strip().lower(): json.dumps(v) if isinstance(v, (list, dict)) else str(v).strip()
                    for k, v in data.items()
                }
        except json.JSONDecodeError:
            pass
        metadata = {}
        for line in cleaned.split("\n"):
            if not line.strip():
                continue
            if ":" in line:
                key, value = line.split(":", 1)
            elif "=" in line:
                key, value = line.split("=", 1)
            else:
                continue
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            if key:
                metadata[key] = value
        if not metadata:
            match = re.search(r'([0-9a-fA-F]{24,})', raw.replace(" ", ""))
            if match:
                metadata["uid"] = match.group(1)
        return metadata

    def _normalize_uid_string(self, value: str) -> str:
        """Normalize UID string to 0x-prefixed uppercase hex."""
        if not value:
            return value
        stripped = value.strip().lower()
        if stripped.startswith("0x"):
            stripped = stripped[2:]
        stripped = re.sub(r'[^0-9a-f]', '', stripped)
        if not stripped:
            return value.strip()
        return "0x" + stripped.upper()

    def _apply_metadata_to_device(self, device: Device, metadata: Dict[str, str]):
        """Update device fields using parsed metadata."""
        if not metadata:
            return
        normalized = {k.lower(): v for k, v in metadata.items()}
        uid_val = normalized.get("uid")
        if uid_val:
            device.uid = self._normalize_uid_string(uid_val)
        if normalized.get("serial_number"):
            device.serial_number = normalized["serial_number"]
        if normalized.get("chip_id"):
            device.chip_id = normalized["chip_id"]
        if normalized.get("mac") or normalized.get("mac_address"):
            device.mac_address = normalized.get("mac_address", normalized.get("mac"))
        if normalized.get("firmware") or normalized.get("firmware_version"):
            device.firmware_version = normalized.get("firmware_version", normalized.get("firmware"))
        if normalized.get("hardware_version"):
            device.hardware_version = normalized["hardware_version"]
        if normalized.get("flash_size"):
            device.flash_size = normalized["flash_size"]
        if normalized.get("cpu_frequency") or normalized.get("cpu_freq"):
            device.cpu_frequency = normalized.get("cpu_frequency", normalized.get("cpu_freq"))
        if normalized.get("manufacturer"):
            device.manufacturer = normalized["manufacturer"]
        if normalized.get("description"):
            device.description = normalized["description"]
        extra = {k: v for k, v in metadata.items() if k not in {
            "uid", "serial_number", "chip_id", "mac", "mac_address", "firmware",
            "firmware_version", "hardware_version", "flash_size", "cpu_frequency",
            "cpu_freq", "manufacturer", "description"
        }}
        if extra:
            device.extra_info.update(extra)

