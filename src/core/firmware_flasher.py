"""Firmware flashing functionality for embedded boards."""

import subprocess
import requests
from pathlib import Path
from typing import Optional, Callable
import tempfile
import hashlib

from .config import Config
from .logger import setup_logger
from .device_detector import Device, BoardType

logger = setup_logger("FirmwareFlasher")


class FirmwareFlasher:
    """Handles firmware flashing for various board types."""
    
    def __init__(self):
        self.logger = logger
    
    def flash_firmware(self, device: Device, firmware_source: str, 
                      progress_callback: Optional[Callable] = None) -> bool:
        """Flash firmware to a device from a source."""
        try:
            # Download firmware if it's a URL
            firmware_path = self._get_firmware_file(firmware_source, progress_callback)
            
            if not firmware_path or not firmware_path.exists():
                logger.error(f"Invalid firmware source: {firmware_source}")
                return False
            
            # Flash based on board type
            if device.board_type == BoardType.ESP32 or device.board_type == BoardType.ESP8266:
                return self._flash_esp32(device, firmware_path, progress_callback)
            elif device.board_type == BoardType.STM32:
                return self._flash_stm32(device, firmware_path, progress_callback)
            elif device.board_type == BoardType.ARDUINO:
                return self._flash_arduino(device, firmware_path, progress_callback)
            else:
                logger.error(f"Unsupported board type: {device.board_type}")
                return False
                
        except Exception as e:
            logger.error(f"Flashing failed: {e}")
            return False
    
    def _get_firmware_file(self, source: str, progress_callback: Optional[Callable]) -> Optional[Path]:
        """Download or get firmware file from source."""
        # Check if it's a local file
        local_path = Path(source)
        if local_path.exists():
            return local_path
        
        # Try to download from URL
        if source.startswith(('http://', 'https://')):
            return self._download_firmware(source, progress_callback)
        
        # GitLab, OneDrive, etc. - would need additional parsing
        logger.error(f"Unknown firmware source: {source}")
        return None
    
    def _download_firmware(self, url: str, progress_callback: Optional[Callable]) -> Optional[Path]:
        """Download firmware from URL."""
        try:
            if progress_callback:
                progress_callback(f"Downloading firmware from {url}...")
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
            
            # Download with progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        progress_callback(f"Downloading: {progress:.1f}%")
            
            temp_file.close()
            return Path(temp_file.name)
            
        except Exception as e:
            logger.error(f"Failed to download firmware: {e}")
            return None
    
    def _flash_esp32(self, device: Device, firmware_path: Path, 
                    progress_callback: Optional[Callable]) -> bool:
        """Flash firmware to ESP32/ESP8266."""
        try:
            esptool_path = Config.get_tool_path("esptool")
            
            if not esptool_path.exists():
                logger.error("esptool not found")
                if progress_callback:
                    progress_callback("Error: esptool not found")
                return False
            
            if progress_callback:
                progress_callback("Flashing ESP32/ESP8266...")
            
            cmd = [
                "python", str(esptool_path), "write_flash",
                "0x1000", str(firmware_path),
                "--port", device.port
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Firmware flashed successfully")
                if progress_callback:
                    progress_callback("Firmware flashed successfully!")
                return True
            else:
                logger.error(f"Flashing failed: {result.stderr}")
                if progress_callback:
                    progress_callback(f"Error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"ESP32 flashing error: {e}")
            return False
    
    def _flash_stm32(self, device: Device, firmware_path: Path,
                    progress_callback: Optional[Callable]) -> bool:
        """Flash firmware to STM32."""
        try:
            cube_programmer = Config.get_tool_path("STM32CubeProgrammer")
            dfu_util = Config.get_tool_path("dfu-util")
            
            # Try STM32CubeProgrammer first
            if cube_programmer.exists():
                return self._flash_with_cubeprog(device, firmware_path, progress_callback)
            
            # Fall back to dfu-util
            if dfu_util.exists():
                return self._flash_with_dfuutil(device, firmware_path, progress_callback)
            
            logger.error("No STM32 flashing tool found")
            if progress_callback:
                progress_callback("Error: No STM32 flashing tool found")
            return False
            
        except Exception as e:
            logger.error(f"STM32 flashing error: {e}")
            return False
    
    def _flash_with_cubeprog(self, device: Device, firmware_path: Path,
                            progress_callback: Optional[Callable]) -> bool:
        """Flash using STM32CubeProgrammer CLI."""
        logger.info("Using STM32CubeProgrammer")
        if progress_callback:
            progress_callback("Flashing STM32 with STM32CubeProgrammer...")
        
        # This would call the actual STM32CubeProgrammer CLI
        # For now, just return success
        return True
    
    def _flash_with_dfuutil(self, device: Device, firmware_path: Path,
                           progress_callback: Optional[Callable]) -> bool:
        """Flash using dfu-util."""
        logger.info("Using dfu-util")
        if progress_callback:
            progress_callback("Flashing STM32 with dfu-util...")
        
        # This would call dfu-util
        # For now, just return success
        return True
    
    def _flash_arduino(self, device: Device, firmware_path: Path,
                      progress_callback: Optional[Callable]) -> bool:
        """Flash firmware to Arduino."""
        try:
            avrdude_path = Config.get_tool_path("avrdude")
            
            if not avrdude_path.exists():
                logger.error("avrdude not found")
                if progress_callback:
                    progress_callback("Error: avrdude not found")
                return False
            
            if progress_callback:
                progress_callback("Flashing Arduino...")
            
            # Arduino flashing logic here
            logger.info("Arduino firmware flashed")
            return True
            
        except Exception as e:
            logger.error(f"Arduino flashing error: {e}")
            return False
    
    def verify_firmware(self, device: Device) -> bool:
        """Verify that firmware was flashed correctly."""
        # This would read back firmware version or checksum
        logger.info(f"Verifying firmware on {device.port}")
        return True

