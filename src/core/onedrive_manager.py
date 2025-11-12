"""OneDrive integration for machine data management."""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import shutil

from .config import Config
from .logger import setup_logger
from .device_detector import Device

logger = setup_logger("OneDriveManager")


class OneDriveManager:
    """Manages OneDrive integration for machine data storage."""
    
    def __init__(self):
        self.logger = logger
        self.config = Config.load_config()
    
    def is_enabled(self) -> bool:
        """Check if OneDrive integration is enabled."""
        return self.config.get('onedrive', {}).get('enabled', False)
    
    def _normalize_path(self, raw: str) -> Path:
        """Normalize user-provided path inputs for Windows and cross‑platform compatibility.
        Handles cases like 'G/' or 'G' by converting to 'G:/', expands env vars, and user home.
        """
        p = os.path.expanduser(os.path.expandvars(raw.strip()))
        # Handle drive letter inputs like 'G' or 'G/'
        if len(p) == 1 and p.isalpha():
            return Path(f"{p}:/")
        if len(p) == 2 and p[1] in ('/', '\\') and p[0].isalpha():
            return Path(f"{p[0]}:/")
        return Path(p)

    def get_base_path(self) -> Optional[Path]:
        """Get the base OneDrive folder path."""
        if not self.is_enabled():
            return None
        
        folder_path = self.config.get('onedrive', {}).get('folder_path', '')
        if not folder_path:
            return None
        
        return self._normalize_path(folder_path)
    
    def get_user_folder_path(self) -> Optional[Path]:
        """Get the user-specific folder path."""
        base_path = self.get_base_path()
        if not base_path:
            return None
        
        user_folder = self.config.get('onedrive', {}).get('user_folder', '')
        if not user_folder:
            return None
        
        return base_path / user_folder
    
    def create_folder_structure(self, operator_name: str, machine_type: str, machine_id: str) -> Optional[Path]:
        """Create the folder structure for a machine."""
        try:
            # Get base user folder
            user_folder = self.get_user_folder_path()
            if not user_folder:
                logger.error("OneDrive user folder not configured")
                return None
            
            # Create user folder if it doesn't exist
            user_folder.mkdir(parents=True, exist_ok=True)
            
            # Create machine type folder
            machine_type_folder = user_folder / machine_type
            machine_type_folder.mkdir(parents=True, exist_ok=True)
            
            # Create machine-specific folder
            machine_folder = machine_type_folder / machine_id
            machine_folder.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Created OneDrive folder structure: {machine_folder}")
            return machine_folder
            
        except Exception as e:
            logger.error(f"Failed to create OneDrive folder structure: {e}")
            return None
    
    def save_machine_data(self, operator_name: str, machine_type: str, machine_id: str, 
                         devices: List[Device], firmware_info: Optional[Dict] = None) -> bool:
        """Save machine data to OneDrive."""
        try:
            if not self.is_enabled():
                logger.info("OneDrive integration disabled")
                return False
            
            # Create folder structure
            machine_folder = self.create_folder_structure(operator_name, machine_type, machine_id)
            if not machine_folder:
                return False
            
            # Create machine data file
            machine_data = {
                "machine_info": {
                    "machine_type": machine_type,
                    "machine_id": machine_id,
                    "operator_name": operator_name,
                    "timestamp": datetime.now().isoformat(),
                    "created_by": "AWG Kumulus Device Manager"
                },
                "devices": [],
                "firmware_history": []
            }
            
            # Add device information
            for device in devices:
                device_data = {
                    "port": device.port,
                    "board_type": device.board_type.value,
                    "vid": f"0x{device.vid:04X}" if device.vid else None,
                    "pid": f"0x{device.pid:04X}" if device.pid else None,
                    "uid": device.uid,
                    "chip_id": device.chip_id,
                    "mac_address": device.mac_address,
                    "manufacturer": device.manufacturer,
                    "serial_number": device.serial_number,
                    "firmware_version": device.firmware_version,
                    "hardware_version": device.hardware_version,
                    "flash_size": device.flash_size,
                    "cpu_frequency": device.cpu_frequency,
                    "detected_at": datetime.now().isoformat()
                }
                machine_data["devices"].append(device_data)
            
            # Add firmware information if provided
            if firmware_info:
                firmware_entry = {
                    "firmware_name": firmware_info.get("name", "Unknown"),
                    "firmware_version": firmware_info.get("version", "Unknown"),
                    "firmware_path": firmware_info.get("path", ""),
                    "firmware_url": firmware_info.get("url", ""),
                    "firmware_size": firmware_info.get("size", 0),
                    "firmware_hash": firmware_info.get("hash", ""),
                    "flashed_at": datetime.now().isoformat(),
                    "flashed_by": operator_name
                }
                machine_data["firmware_history"].append(firmware_entry)
            
            # Save machine data file
            machine_file = machine_folder / f"{machine_id}_data.json"
            with open(machine_file, 'w', encoding='utf-8') as f:
                json.dump(machine_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved machine data to OneDrive: {machine_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save machine data to OneDrive: {e}")
            return False
    
    def save_firmware_file(self, operator_name: str, machine_type: str, machine_id: str,
                          firmware_path: Path, firmware_info: Dict) -> bool:
        """Save firmware file to OneDrive."""
        try:
            if not self.is_enabled():
                return False
            
            # Create folder structure
            machine_folder = self.create_folder_structure(operator_name, machine_type, machine_id)
            if not machine_folder:
                return False
            
            # Create firmware folder
            firmware_folder = machine_folder / "firmware"
            firmware_folder.mkdir(parents=True, exist_ok=True)
            
            # Copy firmware file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            firmware_name = firmware_path.name
            firmware_ext = firmware_path.suffix
            new_firmware_name = f"{timestamp}_{firmware_name}"
            
            destination = firmware_folder / new_firmware_name
            shutil.copy2(firmware_path, destination)
            
            # Save firmware info
            firmware_data = {
                "original_name": firmware_name,
                "stored_name": new_firmware_name,
                "firmware_info": firmware_info,
                "stored_at": datetime.now().isoformat(),
                "stored_by": operator_name,
                "file_size": destination.stat().st_size
            }
            
            info_file = firmware_folder / f"{timestamp}_firmware_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(firmware_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved firmware to OneDrive: {destination}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save firmware to OneDrive: {e}")
            return False
    
    def get_machine_history(self, machine_type: str, machine_id: str) -> Optional[Dict]:
        """Get machine history from OneDrive."""
        try:
            if not self.is_enabled():
                return None
            
            user_folder = self.get_user_folder_path()
            if not user_folder:
                return None
            
            machine_folder = user_folder / machine_type / machine_id
            machine_file = machine_folder / f"{machine_id}_data.json"
            
            if not machine_file.exists():
                return None
            
            with open(machine_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Failed to get machine history: {e}")
            return None
    
    def list_machines(self, machine_type: Optional[str] = None) -> List[Dict]:
        """List all machines in OneDrive."""
        try:
            if not self.is_enabled():
                return []
            
            user_folder = self.get_user_folder_path()
            if not user_folder or not user_folder.exists():
                return []
            
            machines = []
            
            if machine_type:
                # List machines of specific type
                type_folder = user_folder / machine_type
                if type_folder.exists():
                    for machine_folder in type_folder.iterdir():
                        if machine_folder.is_dir():
                            machine_file = machine_folder / f"{machine_folder.name}_data.json"
                            if machine_file.exists():
                                try:
                                    with open(machine_file, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                        machines.append(data["machine_info"])
                                except:
                                    pass
            else:
                # List all machines
                for type_folder in user_folder.iterdir():
                    if type_folder.is_dir():
                        for machine_folder in type_folder.iterdir():
                            if machine_folder.is_dir():
                                machine_file = machine_folder / f"{machine_folder.name}_data.json"
                                if machine_file.exists():
                                    try:
                                        with open(machine_file, 'r', encoding='utf-8') as f:
                                            data = json.load(f)
                                            machines.append(data["machine_info"])
                                    except:
                                        pass
            
            return machines
            
        except Exception as e:
            logger.error(f"Failed to list machines: {e}")
            return []
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test OneDrive connection and folder access.
        If auto-create is enabled, create the base and user folders when missing.
        Prefer testing write access inside the user folder when provided.
        """
        try:
            if not self.is_enabled():
                return False, "OneDrive integration is disabled"

            od_cfg = self.config.get('onedrive', {})
            auto_create = bool(od_cfg.get('auto_create_folders', False))

            base_path = self.get_base_path()
            if not base_path:
                return False, "OneDrive folder path not configured"

            if not base_path.exists():
                if auto_create:
                    try:
                        base_path.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        return False, f"Failed to create base OneDrive folder: {e}"
                else:
                    return False, f"OneDrive folder does not exist: {base_path}"

            # Determine target for write test: prefer user folder if set
            user_folder_path = self.get_user_folder_path()
            target_path = user_folder_path or base_path

            if not target_path.exists():
                if auto_create:
                    try:
                        target_path.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        return False, f"Failed to create user OneDrive folder: {e}"
                else:
                    return False, f"OneDrive user folder does not exist: {target_path}"

            # Test write access
            test_file = target_path / ".test_write_access"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                return False, f"No write access to OneDrive folder: {e}"

            location = "user folder" if user_folder_path else "base folder"
            return True, f"OneDrive connection successful (write access verified in {location})"

        except Exception as e:
            return False, f"OneDrive test failed: {e}"
