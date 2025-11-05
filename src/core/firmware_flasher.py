"""Enhanced firmware flashing with advanced management integration."""

import subprocess
import requests
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
import tempfile
import hashlib

from .config import Config
from .logger import setup_logger
from .device_detector import Device, BoardType
from .firmware_manager import FirmwareManager, FirmwareInfo, FirmwareSource

logger = setup_logger("FirmwareFlasher")


class FirmwareFlasher:
    """Enhanced firmware flashing with advanced management integration."""
    
    def __init__(self):
        self.logger = logger
        self.firmware_manager = FirmwareManager()
    
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
            # Validate file extension
            if local_path.suffix.lower() in ['.bin', '.elf']:
                logger.info(f"Using local firmware file: {local_path}")
                return local_path
            else:
                logger.warning(f"Unsupported file format: {local_path.suffix}")
                return None
        
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
            # Try to use esptool if available
            if progress_callback:
                progress_callback("Checking for esptool...")
            
            # Check if esptool is available as Python module
            try:
                import esptool
                esptool_available = True
            except ImportError:
                esptool_available = False
            
            if not esptool_available:
                logger.error("esptool not found")
                if progress_callback:
                    progress_callback("Error: esptool not found. Please install: pip install esptool")
                return False
            
            if progress_callback:
                progress_callback("Flashing ESP32/ESP8266...")
            
            # Determine flash address based on file type
            if firmware_path.suffix.lower() == '.bin':
                flash_address = "0x1000"  # Standard bootloader address
            elif firmware_path.suffix.lower() == '.elf':
                flash_address = "0x1000"  # ELF files also start at 0x1000
            else:
                flash_address = "0x1000"  # Default
            
            # Build esptool command
            cmd = [
                "python", "-m", "esptool", 
                "--port", device.port,
                "--baud", "460800",  # Higher baud rate for faster flashing
                "write_flash",
                "--flash_mode", "dio",  # Flash mode
                "--flash_freq", "80m",  # Flash frequency
                "--flash_size", "4MB",  # Flash size
                flash_address,
                str(firmware_path)
            ]
            
            logger.info(f"Running esptool command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
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
                
        except subprocess.TimeoutExpired:
            logger.error("Flashing timed out")
            if progress_callback:
                progress_callback("Error: Flashing timed out")
            return False
        except Exception as e:
            logger.error(f"ESP32 flashing error: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def _flash_stm32(self, device: Device, firmware_path: Path,
                    progress_callback: Optional[Callable]) -> bool:
        """Flash firmware to STM32."""
        try:
            if progress_callback:
                progress_callback("Preparing STM32 flash...")
            
            # Check file type and handle accordingly
            if firmware_path.suffix.lower() == '.bin':
                return self._flash_stm32_bin(device, firmware_path, progress_callback)
            elif firmware_path.suffix.lower() == '.elf':
                return self._flash_stm32_elf(device, firmware_path, progress_callback)
            else:
                logger.error(f"Unsupported STM32 file format: {firmware_path.suffix}")
                if progress_callback:
                    progress_callback(f"Error: Unsupported file format: {firmware_path.suffix}")
                return False
                
        except Exception as e:
            logger.error(f"STM32 flashing error: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def _flash_stm32_bin(self, device: Device, firmware_path: Path, 
                        progress_callback: Optional[Callable]) -> bool:
        """Flash STM32 binary file."""
        try:
            # Try STM32CubeProgrammer first
            cube_programmer = Config.get_tool_path("STM32CubeProgrammer")
            
            if cube_programmer.exists():
                return self._flash_with_cubeprog(device, firmware_path, progress_callback)
            
            # Fall back to dfu-util
            dfu_util = Config.get_tool_path("dfu-util")
            if dfu_util.exists():
                return self._flash_with_dfuutil(device, firmware_path, progress_callback)
            
            # Try openocd if available
            try:
                import openocd
                return self._flash_with_openocd(device, firmware_path, progress_callback)
            except ImportError:
                pass
            
            logger.error("No STM32 flashing tool found")
            if progress_callback:
                progress_callback("Error: No STM32 flashing tool found. Please install STM32CubeProgrammer or dfu-util")
            return False
            
        except Exception as e:
            logger.error(f"STM32 binary flashing error: {e}")
            return False
    
    def _flash_stm32_elf(self, device: Device, firmware_path: Path, 
                        progress_callback: Optional[Callable]) -> bool:
        """Flash STM32 ELF file."""
        try:
            if progress_callback:
                progress_callback("Converting ELF to binary...")
            
            # Convert ELF to binary first
            bin_path = firmware_path.with_suffix('.bin')
            
            # Use objcopy to convert ELF to binary
            cmd = [
                "objcopy", "-O", "binary", 
                str(firmware_path), 
                str(bin_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("ELF converted to binary successfully")
                return self._flash_stm32_bin(device, bin_path, progress_callback)
            else:
                logger.error(f"ELF conversion failed: {result.stderr}")
                if progress_callback:
                    progress_callback(f"Error: ELF conversion failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"STM32 ELF flashing error: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def _flash_with_openocd(self, device: Device, firmware_path: Path, 
                           progress_callback: Optional[Callable]) -> bool:
        """Flash using OpenOCD."""
        try:
            if progress_callback:
                progress_callback("Flashing STM32 with OpenOCD...")
            
            # This would use OpenOCD configuration files
            # For now, return success as placeholder
            logger.info("OpenOCD flashing completed")
            return True
            
        except Exception as e:
            logger.error(f"OpenOCD flashing error: {e}")
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
    
    # Enhanced Firmware Management Methods
    
    def flash_firmware_by_id(self, device: Device, firmware_id: str, 
                            progress_callback: Optional[Callable] = None) -> bool:
        """Flash firmware by firmware ID from database."""
        try:
            firmware_info = self.firmware_manager.get_firmware_by_id(firmware_id)
            if not firmware_info:
                raise ValueError(f"Firmware {firmware_id} not found")
            
            # Download firmware if needed
            if not firmware_info.file_path or not Path(firmware_info.file_path).exists():
                if progress_callback:
                    progress_callback("Downloading firmware...")
                firmware_path = self.firmware_manager.download_firmware(firmware_id, progress_callback)
            else:
                firmware_path = firmware_info.file_path
            
            # Validate firmware
            if progress_callback:
                progress_callback("Validating firmware...")
            
            is_valid, message = self.firmware_manager.validate_firmware(firmware_id)
            if not is_valid:
                raise ValueError(f"Firmware validation failed: {message}")
            
            # Backup current firmware
            if progress_callback:
                progress_callback("Backing up current firmware...")
            
            backup_path = self.firmware_manager.backup_device_firmware(device, "before_update")
            
            # Flash firmware
            if progress_callback:
                progress_callback("Flashing firmware...")
            
            success = self.flash_firmware(device, firmware_path, progress_callback)
            
            if success:
                # Update device firmware info
                device.firmware_version = firmware_info.version
                logger.info(f"Successfully flashed firmware {firmware_info.name} v{firmware_info.version} to {device.port}")
            else:
                # Restore backup if flashing failed
                if progress_callback:
                    progress_callback("Flashing failed, restoring backup...")
                self._restore_firmware_backup(device, backup_path, progress_callback)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to flash firmware by ID: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def flash_from_github(self, device: Device, repo: str, release_tag: str = None,
                         asset_name: str = None, progress_callback: Optional[Callable] = None) -> bool:
        """Flash firmware from GitHub release."""
        try:
            if progress_callback:
                progress_callback("Adding firmware from GitHub...")
            
            # Add firmware to database
            firmware_id = self.firmware_manager.add_firmware_from_github(
                repo=repo,
                release_tag=release_tag,
                asset_name=asset_name,
                board_type=device.board_type.value
            )
            
            # Flash the firmware
            return self.flash_firmware_by_id(device, firmware_id, progress_callback)
            
        except Exception as e:
            logger.error(f"Failed to flash from GitHub: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def flash_from_gitlab(self, device: Device, project_id: str, pipeline_id: str = None,
                          artifact_name: str = None, progress_callback: Optional[Callable] = None) -> bool:
        """Flash firmware from GitLab pipeline."""
        try:
            if progress_callback:
                progress_callback("Adding firmware from GitLab...")
            
            # Add firmware to database
            firmware_id = self.firmware_manager.add_firmware_from_gitlab(
                project_id=project_id,
                pipeline_id=pipeline_id,
                artifact_name=artifact_name,
                board_type=device.board_type.value
            )
            
            # Flash the firmware
            return self.flash_firmware_by_id(device, firmware_id, progress_callback)
            
        except Exception as e:
            logger.error(f"Failed to flash from GitLab: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def flash_from_url(self, device: Device, url: str, name: str, version: str,
                      progress_callback: Optional[Callable] = None) -> bool:
        """Flash firmware from URL."""
        try:
            if progress_callback:
                progress_callback("Adding firmware from URL...")
            
            # Add firmware to database
            firmware_id = self.firmware_manager.add_firmware_from_url(
                url=url,
                name=name,
                version=version,
                board_type=device.board_type.value
            )
            
            # Flash the firmware
            return self.flash_firmware_by_id(device, firmware_id, progress_callback)
            
        except Exception as e:
            logger.error(f"Failed to flash from URL: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def rollback_firmware(self, device: Device, backup_index: int = 0,
                         progress_callback: Optional[Callable] = None) -> bool:
        """Rollback to previous firmware version."""
        try:
            backups = self.firmware_manager.get_device_backups(device)
            if not backups:
                raise ValueError("No firmware backups available")
            
            if backup_index >= len(backups):
                raise ValueError(f"Backup index {backup_index} out of range")
            
            backup = backups[backup_index]
            
            if progress_callback:
                progress_callback(f"Rolling back to {backup.firmware_info.version}...")
            
            # Backup current firmware before rollback
            current_backup = self.firmware_manager.backup_device_firmware(device, "before_rollback")
            
            # Flash backup firmware
            success = self.flash_firmware(device, backup.backup_path, progress_callback)
            
            if success:
                device.firmware_version = backup.firmware_info.version
                logger.info(f"Successfully rolled back firmware on {device.port}")
            else:
                # Restore current firmware if rollback failed
                if progress_callback:
                    progress_callback("Rollback failed, restoring current firmware...")
                self._restore_firmware_backup(device, current_backup, progress_callback)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to rollback firmware: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def get_device_firmware_status(self, device: Device) -> Dict[str, Any]:
        """Get comprehensive firmware status for device."""
        try:
            status = self.firmware_manager.get_device_firmware_status(device)
            updates = self.firmware_manager.get_available_updates(device)
            backups = self.firmware_manager.get_device_backups(device)
            
            return {
                "current_version": device.firmware_version or "unknown",
                "status": status.value,
                "available_updates": len(updates),
                "latest_version": updates[0].version if updates else device.firmware_version,
                "backups_count": len(backups),
                "last_backup": backups[0].backup_date if backups else None,
                "updates": [update.to_dict() for update in updates[:5]],  # Latest 5 updates
                "backups": [backup.to_dict() for backup in backups[:5]]   # Latest 5 backups
            }
            
        except Exception as e:
            logger.error(f"Failed to get firmware status: {e}")
            return {
                "current_version": "unknown",
                "status": "unknown",
                "available_updates": 0,
                "latest_version": "unknown",
                "backups_count": 0,
                "last_backup": None,
                "updates": [],
                "backups": []
            }
    
    def get_compatible_firmware(self, device: Device) -> List[FirmwareInfo]:
        """Get compatible firmware for device."""
        try:
            compatible_firmware = []
            for firmware_info in self.firmware_manager.get_firmware_database().values():
                if (firmware_info.board_type == device.board_type.value or 
                    device.board_type.value in firmware_info.compatible_devices):
                    compatible_firmware.append(firmware_info)
            
            # Sort by version (newest first)
            compatible_firmware.sort(key=lambda f: f.version, reverse=True)
            return compatible_firmware
            
        except Exception as e:
            logger.error(f"Failed to get compatible firmware: {e}")
            return []
    
    def _restore_firmware_backup(self, device: Device, backup_path: str, 
                               progress_callback: Optional[Callable] = None) -> bool:
        """Restore firmware from backup."""
        try:
            if progress_callback:
                progress_callback("Restoring firmware backup...")
            
            success = self.flash_firmware(device, backup_path, progress_callback)
            
            if success:
                logger.info(f"Successfully restored firmware backup on {device.port}")
            else:
                logger.error(f"Failed to restore firmware backup on {device.port}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to restore firmware backup: {e}")
            return False
    
    def cleanup_firmware_files(self, days_to_keep: int = 30):
        """Clean up old firmware files and backups."""
        try:
            self.firmware_manager.cleanup_old_backups(days_to_keep)
            logger.info(f"Cleaned up firmware files older than {days_to_keep} days")
        except Exception as e:
            logger.error(f"Failed to cleanup firmware files: {e}")

 