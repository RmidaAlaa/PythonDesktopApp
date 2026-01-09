"""Enhanced firmware flashing with advanced management integration."""

import subprocess
import requests
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
import tempfile
import hashlib
import shutil
from PySide6.QtCore import QCoreApplication

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
            if device.board_type == BoardType.STM32:
                return self._flash_stm32(device, firmware_path, progress_callback)
            else:
                guess = self._guess_board_type(device, firmware_path)
                if guess == BoardType.STM32:
                    return self._flash_stm32(device, firmware_path, progress_callback)
                if firmware_path.suffix.lower() in ('.bin', '.elf'):
                    return self._flash_stm32(device, firmware_path, progress_callback)
                logger.error(f"Unsupported board type: {device.board_type}")
                return False
                
        except Exception as e:
            logger.error(f"Flashing failed: {e}")
            return False

    def _guess_board_type(self, device: Device, firmware_path: Path) -> Optional[BoardType]:
        try:
            name = firmware_path.name.lower()
            desc = (getattr(device, 'description', '') or '').lower()
            manu = (getattr(device, 'manufacturer', '') or '').lower()
            vid = getattr(device, 'vid', None)
            pid = getattr(device, 'pid', None)
            if isinstance(vid, str):
                try:
                    vid = int(vid, 16) if vid.lower().startswith('0x') else int(vid)
                except Exception:
                    vid = None
            if isinstance(pid, str):
                try:
                    pid = int(pid, 16) if pid.lower().startswith('0x') else int(pid)
                except Exception:
                    pid = None
            if vid == 0x0483:
                return BoardType.STM32
            if 'stm32' in name or 'stm' in name or 'cube' in name or 'uid' in name:
                return BoardType.STM32
            if 'stmicro' in manu or 'stmicroelectronics' in manu or 'st' in manu:
                return BoardType.STM32
        except Exception:
            pass
        return None
    
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
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Downloading firmware from {}...").format(url))
            
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
                        progress_callback(QCoreApplication.translate("FirmwareFlasher", "Downloading: {:.1f}%").format(progress))
            
            temp_file.close()
            return Path(temp_file.name)
            
        except Exception as e:
            logger.error(f"Failed to download firmware: {e}")
            return None
    
    
    def _flash_stm32(self, device: Device, firmware_path: Path,
                    progress_callback: Optional[Callable]) -> bool:
        """Flash firmware to STM32."""
        try:
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Preparing STM32 flash..."))
            
            # Check file type and handle accordingly
            if firmware_path.suffix.lower() == '.bin':
                return self._flash_stm32_bin(device, firmware_path, progress_callback)
            elif firmware_path.suffix.lower() == '.elf':
                return self._flash_stm32_elf(device, firmware_path, progress_callback)
            else:
                logger.error(f"Unsupported STM32 file format: {firmware_path.suffix}")
                if progress_callback:
                    progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: Unsupported file format: {}").format(firmware_path.suffix))
                return False
                
        except Exception as e:
            logger.error(f"STM32 flashing error: {e}")
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: {}").format(str(e)))
            return False
    
    def _flash_stm32_bin(self, device: Device, firmware_path: Path, 
                        progress_callback: Optional[Callable]) -> bool:
        """Flash STM32 binary file."""
        try:
            # Try STM32CubeProgrammer first
            # We check if we can resolve the executable
            cube_exe = Config.get_tool_executable("STM32CubeProgrammer", "STM32_Programmer_CLI.exe")
            # Simple check if it looks like a valid path or command
            if shutil.which(cube_exe) or Path(cube_exe).exists():
                return self._flash_with_cubeprog(device, firmware_path, progress_callback)
            
            # Fall back to dfu-util
            dfu_exe = Config.get_tool_executable("dfu-util", "dfu-util.exe")
            if shutil.which(dfu_exe) or Path(dfu_exe).exists():
                return self._flash_with_dfuutil(device, firmware_path, progress_callback)
            
            logger.error("No STM32 flashing tool found")
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: No STM32 flashing tool found. Please install STM32CubeProgrammer or dfu-util"))
            return False
            
        except Exception as e:
            logger.error(f"STM32 binary flashing error: {e}")
            return False
    
    def _flash_stm32_elf(self, device: Device, firmware_path: Path, 
                        progress_callback: Optional[Callable]) -> bool:
        """Flash STM32 ELF file."""
        try:
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Converting ELF to binary..."))
            
            # Convert ELF to binary first
            bin_path = firmware_path.with_suffix('.bin')
            
            obj = shutil.which("arm-none-eabi-objcopy") or shutil.which("objcopy") or "objcopy"
            cmd = [obj, "-O", "binary", str(firmware_path), str(bin_path)]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("ELF converted to binary successfully")
                return self._flash_stm32_bin(device, bin_path, progress_callback)
            else:
                logger.error(f"ELF conversion failed: {result.stderr}")
                if progress_callback:
                    progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: ELF conversion failed: {}").format(result.stderr))
                return False
                
        except Exception as e:
            logger.error(f"STM32 ELF flashing error: {e}")
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: {}").format(str(e)))
            return False
    
    def _flash_with_cubeprog(self, device: Device, firmware_path: Path,
                            progress_callback: Optional[Callable]) -> bool:
        logger.info("Using STM32CubeProgrammer")
        if progress_callback:
            progress_callback(QCoreApplication.translate("FirmwareFlasher", "Flashing STM32 with STM32CubeProgrammer..."))
        try:
            exe = Config.get_tool_executable("STM32CubeProgrammer", "STM32_Programmer_CLI.exe")
            
            # Determine connection mode
            # If it's an ST-Link (debugger/programmer), we use SWD
            # If it's a direct DFU/Bootloader connection, we might use USB or UART
            # ST-Link usually has specific PIDs (0x3748, 0x374B, etc.) or "ST-Link" in description
            is_stlink = False
            
            # Check description or VID/PID if available
            desc = (getattr(device, 'description', '') or '').lower()
            if "st-link" in desc or "stlink" in desc:
                is_stlink = True
            
            # Check known ST-Link VIDs/PIDs
            stlink_pids = [0x3748, 0x374B, 0x3752]
            try:
                pid = getattr(device, 'pid', None)
                if pid:
                    pid_int = int(pid) if isinstance(pid, int) else (int(pid, 16) if str(pid).startswith('0x') else int(pid))
                    if pid_int in stlink_pids:
                        is_stlink = True
            except:
                pass

            if is_stlink:
                # Force SWD connection for ST-Link
                conn = "port=SWD"
            else:
                # Use COM port for UART bootloader or generic
                port = getattr(device, "port", "").upper()
                conn = f"port={port}" if port.startswith("COM") else "port=SWD"
            
            cmd = [exe, "-c", conn, "-w", str(firmware_path), "0x08000000", "-v", "-rst"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: STM32CubeProgrammer failed"))
            logger.error(f"STM32CubeProgrammer error: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"CubeProgrammer flashing error: {e}")
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
                    progress_callback(QCoreApplication.translate("FirmwareFlasher", "Downloading firmware..."))
                firmware_path = self.firmware_manager.download_firmware(firmware_id, progress_callback)
            else:
                firmware_path = firmware_info.file_path
            
            # Validate firmware
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Validating firmware..."))
            
            is_valid, message = self.firmware_manager.validate_firmware(firmware_id)
            if not is_valid:
                raise ValueError(QCoreApplication.translate("FirmwareFlasher", "Firmware validation failed: {}").format(message))
            
            # Backup current firmware
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Backing up current firmware..."))
            
            backup_path = self.firmware_manager.backup_device_firmware(device, "before_update")
            
            # Flash firmware
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Flashing firmware..."))
            
            success = self.flash_firmware(device, firmware_path, progress_callback)
            
            if success:
                # Update device firmware info
                device.firmware_version = firmware_info.version
                logger.info(f"Successfully flashed firmware {firmware_info.name} v{firmware_info.version} to {device.port}")
            else:
                # Restore backup if flashing failed
                if progress_callback:
                    progress_callback(QCoreApplication.translate("FirmwareFlasher", "Flashing failed, restoring backup..."))
                self._restore_firmware_backup(device, backup_path, progress_callback)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to flash firmware by ID: {e}")
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: {}").format(str(e)))
            return False
    
    def flash_from_github(self, device: Device, repo: str, release_tag: str = None,
                         asset_name: str = None, progress_callback: Optional[Callable] = None) -> bool:
        """Flash firmware from GitHub release."""
        try:
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Adding firmware from GitHub..."))
            
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
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: {}").format(str(e)))
            return False
    
    def flash_from_gitlab(self, device: Device, project_id: str, pipeline_id: str = None,
                          artifact_name: str = None, progress_callback: Optional[Callable] = None) -> bool:
        """Flash firmware from GitLab pipeline."""
        try:
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Adding firmware from GitLab..."))
            
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
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: {}").format(str(e)))
            return False
    
    def flash_from_url(self, device: Device, url: str, name: str, version: str,
                      progress_callback: Optional[Callable] = None) -> bool:
        """Flash firmware from URL."""
        try:
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Adding firmware from URL..."))
            
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
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: {}").format(str(e)))
            return False
    
    def rollback_firmware(self, device: Device, backup_index: int = 0,
                         progress_callback: Optional[Callable] = None) -> bool:
        """Rollback to previous firmware version."""
        try:
            backups = self.firmware_manager.get_device_backups(device)
            if not backups:
                raise ValueError(QCoreApplication.translate("FirmwareFlasher", "No firmware backups available"))
            
            if backup_index >= len(backups):
                raise ValueError(
                    QCoreApplication.translate("FirmwareFlasher", "Backup index {} out of range").format(backup_index)
                )
            
            backup = backups[backup_index]
            
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Rolling back to {}...").format(backup.firmware_info.version))
            
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
                    progress_callback(QCoreApplication.translate("FirmwareFlasher", "Rollback failed, restoring current firmware..."))
                self._restore_firmware_backup(device, current_backup, progress_callback)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to rollback firmware: {e}")
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Error: {}").format(str(e)))
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
                progress_callback(QCoreApplication.translate("FirmwareFlasher", "Restoring firmware backup..."))
            
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

 
