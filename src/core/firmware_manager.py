"""Advanced firmware management system with GitHub/GitLab integration."""

import json
import hashlib
import requests
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from PySide6.QtCore import QCoreApplication

from .logger import setup_logger
from .config import Config
from .device_detector import Device

logger = setup_logger("FirmwareManager")


class FirmwareSource(Enum):
    """Firmware source types."""
    LOCAL_FILE = "local_file"
    GITHUB_RELEASE = "github_release"
    GITHUB_ACTION = "github_action"
    GITLAB_PIPELINE = "gitlab_pipeline"
    GITLAB_RELEASE = "gitlab_release"
    URL_DOWNLOAD = "url_download"


class FirmwareStatus(Enum):
    """Firmware status types."""
    INSTALLED = "installed"
    AVAILABLE = "available"
    OUTDATED = "outdated"
    LATEST = "latest"
    UNKNOWN = "unknown"


@dataclass
class FirmwareInfo:
    """Firmware information."""
    name: str
    version: str
    source: FirmwareSource
    url: Optional[str] = None
    file_path: Optional[str] = None
    checksum: Optional[str] = None
    checksum_type: str = "sha256"
    size: int = 0
    board_type: Optional[str] = None
    compatible_devices: List[str] = None
    release_notes: Optional[str] = None
    release_date: Optional[str] = None
    author: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = None
    commit_hash: Optional[str] = None
    download_count: int = 0
    status: FirmwareStatus = FirmwareStatus.UNKNOWN
    
    def __post_init__(self):
        if self.compatible_devices is None:
            self.compatible_devices = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['source'] = self.source.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FirmwareInfo':
        """Create from dictionary."""
        data['source'] = FirmwareSource(data['source'])
        data['status'] = FirmwareStatus(data['status'])
        return cls(**data)


@dataclass
class FirmwareBackup:
    """Firmware backup information."""
    device_id: str
    firmware_info: FirmwareInfo
    backup_path: str
    backup_date: str
    backup_reason: str = "manual"
    original_firmware: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['firmware_info'] = self.firmware_info.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FirmwareBackup':
        """Create from dictionary."""
        data['firmware_info'] = FirmwareInfo.from_dict(data['firmware_info'])
        return cls(**data)


class FirmwareManager:
    """Advanced firmware management system."""
    
    def __init__(self):
        self.logger = logger
        self.firmware_database: Dict[str, FirmwareInfo] = {}
        self.firmware_backups: Dict[str, List[FirmwareBackup]] = {}
        self.device_firmware: Dict[str, FirmwareInfo] = {}  # device_id -> current firmware
        
        # File paths
        self.app_data_dir = Path(Config.get_app_data_dir())
        self.firmware_db_file = self.app_data_dir / "firmware_database.json"
        self.backups_dir = self.app_data_dir / "firmware_backups"
        self.downloads_dir = self.app_data_dir / "firmware_downloads"
        
        # Create directories
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        
        # Load data
        self._load_firmware_database()
        self._load_firmware_backups()
    
    def _load_firmware_database(self):
        """Load firmware database from file."""
        try:
            if self.firmware_db_file.exists():
                with open(self.firmware_db_file, 'r') as f:
                    data = json.load(f)
                    for firmware_id, firmware_data in data.items():
                        self.firmware_database[firmware_id] = FirmwareInfo.from_dict(firmware_data)
                logger.info(f"Loaded {len(self.firmware_database)} firmware entries")
        except Exception as e:
            logger.warning(f"Failed to load firmware database: {e}")
    
    def _save_firmware_database(self):
        """Save firmware database to file."""
        try:
            data = {}
            for firmware_id, firmware_info in self.firmware_database.items():
                data[firmware_id] = firmware_info.to_dict()
            
            with open(self.firmware_db_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Firmware database saved")
        except Exception as e:
            logger.error(f"Failed to save firmware database: {e}")
    
    def _load_firmware_backups(self):
        """Load firmware backups from file."""
        try:
            backups_file = self.app_data_dir / "firmware_backups.json"
            if backups_file.exists():
                with open(backups_file, 'r') as f:
                    data = json.load(f)
                    for device_id, backups_data in data.items():
                        self.firmware_backups[device_id] = [
                            FirmwareBackup.from_dict(backup_data) 
                            for backup_data in backups_data
                        ]
                logger.info(f"Loaded firmware backups for {len(self.firmware_backups)} devices")
        except Exception as e:
            logger.warning(f"Failed to load firmware backups: {e}")
    
    def _save_firmware_backups(self):
        """Save firmware backups to file."""
        try:
            backups_file = self.app_data_dir / "firmware_backups.json"
            data = {}
            for device_id, backups in self.firmware_backups.items():
                data[device_id] = [backup.to_dict() for backup in backups]
            
            with open(backups_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Firmware backups saved")
        except Exception as e:
            logger.error(f"Failed to save firmware backups: {e}")
    
    def add_firmware_from_file(self, file_path: str, name: str, version: str, 
                              board_type: str = None, compatible_devices: List[str] = None) -> str:
        """Add firmware from local file."""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(
                    QCoreApplication.translate("FirmwareManager", "Firmware file not found: {}").format(file_path)
                )
            
            # Calculate checksum
            checksum = self._calculate_file_checksum(file_path)
            
            # Get file size
            file_size = file_path.stat().st_size
            
            firmware_info = FirmwareInfo(
                name=name,
                version=version,
                source=FirmwareSource.LOCAL_FILE,
                file_path=str(file_path),
                checksum=checksum,
                size=file_size,
                board_type=board_type,
                compatible_devices=compatible_devices or [],
                release_date=datetime.now().isoformat()
            )
            
            firmware_id = self._generate_firmware_id(firmware_info)
            self.firmware_database[firmware_id] = firmware_info
            self._save_firmware_database()
            
            logger.info(f"Added firmware from file: {name} v{version}")
            return firmware_id
            
        except Exception as e:
            logger.error(f"Failed to add firmware from file: {e}")
            raise
    
    def add_firmware_from_github(self, repo: str, release_tag: str = None, 
                               asset_name: str = None, board_type: str = None) -> str:
        """Add firmware from GitHub release."""
        try:
            # Parse repository (owner/repo)
            if '/' not in repo:
                raise ValueError(
                    QCoreApplication.translate(
                        "FirmwareManager",
                        "Repository must be in format 'owner/repo'"
                    )
                )
            
            owner, repo_name = repo.split('/', 1)
            
            # Get release information
            if release_tag:
                release_url = f"https://api.github.com/repos/{owner}/{repo_name}/releases/tags/{release_tag}"
            else:
                release_url = f"https://api.github.com/repos/{owner}/{repo_name}/releases/latest"
            
            response = requests.get(release_url, timeout=30)
            response.raise_for_status()
            release_data = response.json()
            
            # Find firmware asset
            assets = release_data.get('assets', [])
            if asset_name:
                asset = next((a for a in assets if asset_name in a['name']), None)
            else:
                # Look for common firmware file extensions
                firmware_extensions = ['.bin', '.elf', '.hex', '.uf2']
                asset = next((a for a in assets if any(a['name'].endswith(ext) for ext in firmware_extensions)), None)
            
            if not asset:
                raise ValueError(
                    QCoreApplication.translate(
                        "FirmwareManager",
                        "No suitable firmware asset found in release"
                    )
                )
            
            firmware_info = FirmwareInfo(
                name=asset['name'],
                version=release_data['tag_name'],
                source=FirmwareSource.GITHUB_RELEASE,
                url=asset['browser_download_url'],
                checksum=None,  # Will be calculated when downloaded
                size=asset['size'],
                board_type=board_type,
                compatible_devices=[],
                release_notes=release_data.get('body', ''),
                release_date=release_data['published_at'],
                author=release_data['author']['login'],
                repository=repo,
                branch=release_data['target_commitish']
            )
            
            firmware_id = self._generate_firmware_id(firmware_info)
            self.firmware_database[firmware_id] = firmware_info
            self._save_firmware_database()
            
            logger.info(f"Added firmware from GitHub: {repo} v{release_data['tag_name']}")
            return firmware_id
            
        except Exception as e:
            logger.error(f"Failed to add firmware from GitHub: {e}")
            raise
    
    def add_firmware_from_gitlab(self, project_id: str, pipeline_id: str = None,
                                artifact_name: str = None, board_type: str = None) -> str:
        """Add firmware from GitLab pipeline artifact."""
        try:
            # Get pipeline information
            if pipeline_id:
                pipeline_url = f"https://gitlab.com/api/v4/projects/{project_id}/pipelines/{pipeline_id}"
            else:
                # Get latest successful pipeline
                pipelines_url = f"https://gitlab.com/api/v4/projects/{project_id}/pipelines"
                response = requests.get(pipelines_url, params={'status': 'success', 'per_page': 1}, timeout=30)
                response.raise_for_status()
                pipelines = response.json()
                if not pipelines:
                    raise ValueError(
                        QCoreApplication.translate(
                            "FirmwareManager",
                            "No successful pipelines found"
                        )
                    )
                pipeline_id = pipelines[0]['id']
                pipeline_url = f"https://gitlab.com/api/v4/projects/{project_id}/pipelines/{pipeline_id}"
            
            response = requests.get(pipeline_url, timeout=30)
            response.raise_for_status()
            pipeline_data = response.json()
            
            # Get job artifacts
            jobs_url = f"https://gitlab.com/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs"
            response = requests.get(jobs_url, timeout=30)
            response.raise_for_status()
            jobs = response.json()
            
            # Find job with firmware artifacts
            firmware_job = None
            for job in jobs:
                if job['status'] == 'success' and job['artifacts_file']:
                    if artifact_name:
                        if artifact_name in job['name']:
                            firmware_job = job
                            break
                    else:
                        # Look for common firmware job names
                        firmware_jobs = ['build', 'firmware', 'compile', 'release']
                        if any(name in job['name'].lower() for name in firmware_jobs):
                            firmware_job = job
                            break
            
            if not firmware_job:
                raise ValueError(
                    QCoreApplication.translate(
                        "FirmwareManager",
                        "No suitable firmware job found in pipeline"
                    )
                )
            
            # Get artifact download URL
            artifact_url = f"https://gitlab.com/api/v4/projects/{project_id}/jobs/{firmware_job['id']}/artifacts"
            
            firmware_info = FirmwareInfo(
                name=f"{firmware_job['name']}_artifacts",
                version=pipeline_data['ref'],
                source=FirmwareSource.GITLAB_PIPELINE,
                url=artifact_url,
                checksum=None,
                size=0,  # Will be determined when downloaded
                board_type=board_type,
                compatible_devices=[],
                release_notes=f"Pipeline {pipeline_id}",
                release_date=pipeline_data['created_at'],
                author=pipeline_data['user']['username'],
                repository=f"project_{project_id}",
                branch=pipeline_data['ref']
            )
            
            firmware_id = self._generate_firmware_id(firmware_info)
            self.firmware_database[firmware_id] = firmware_info
            self._save_firmware_database()
            
            logger.info(f"Added firmware from GitLab: Project {project_id}, Pipeline {pipeline_id}")
            return firmware_id
            
        except Exception as e:
            logger.error(f"Failed to add firmware from GitLab: {e}")
            raise
    
    def add_firmware_from_url(self, url: str, name: str, version: str,
                             board_type: str = None, compatible_devices: List[str] = None) -> str:
        """Add firmware from URL."""
        try:
            # Get file information from URL
            response = requests.head(url, timeout=30)
            response.raise_for_status()
            
            content_length = response.headers.get('content-length')
            file_size = int(content_length) if content_length else 0
            
            firmware_info = FirmwareInfo(
                name=name,
                version=version,
                source=FirmwareSource.URL_DOWNLOAD,
                url=url,
                checksum=None,  # Will be calculated when downloaded
                size=file_size,
                board_type=board_type,
                compatible_devices=compatible_devices or [],
                release_date=datetime.now().isoformat()
            )
            
            firmware_id = self._generate_firmware_id(firmware_info)
            self.firmware_database[firmware_id] = firmware_info
            self._save_firmware_database()
            
            logger.info(f"Added firmware from URL: {name} v{version}")
            return firmware_id
            
        except Exception as e:
            logger.error(f"Failed to add firmware from URL: {e}")
            raise
    
    def download_firmware(self, firmware_id: str, progress_callback=None) -> str:
        """Download firmware file."""
        try:
            if firmware_id not in self.firmware_database:
                raise ValueError(
                    QCoreApplication.translate("FirmwareManager", "Firmware {} not found").format(firmware_id)
                )
            
            firmware_info = self.firmware_database[firmware_id]
            
            # If already downloaded and file exists, return path
            if firmware_info.file_path and Path(firmware_info.file_path).exists():
                return firmware_info.file_path
            
            # Download file
            if not firmware_info.url:
                raise ValueError(
                    QCoreApplication.translate("FirmwareManager", "No download URL available")
                )
            
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareManager", "Downloading {}...").format(firmware_info.name))
            
            response = requests.get(firmware_info.url, stream=True, timeout=300)
            response.raise_for_status()
            
            # Determine file extension
            file_ext = self._get_file_extension_from_url(firmware_info.url)
            if not file_ext:
                file_ext = '.bin'  # Default extension
            
            # Create download path
            download_filename = f"{firmware_id}_{firmware_info.name}{file_ext}"
            download_path = self.downloads_dir / download_filename
            
            # Download with progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            progress_callback(QCoreApplication.translate("FirmwareManager", "Downloading {}... {}%").format(firmware_info.name, progress))
            
            # Update firmware info
            firmware_info.file_path = str(download_path)
            firmware_info.size = download_path.stat().st_size
            firmware_info.checksum = self._calculate_file_checksum(download_path)
            
            self._save_firmware_database()
            
            if progress_callback:
                progress_callback(QCoreApplication.translate("FirmwareManager", "Downloaded {} successfully").format(firmware_info.name))
            
            logger.info(f"Downloaded firmware: {firmware_info.name}")
            return str(download_path)
            
        except Exception as e:
            logger.error(f"Failed to download firmware: {e}")
            raise
    
    def validate_firmware(self, firmware_id: str) -> Tuple[bool, str]:
        """Validate firmware integrity."""
        try:
            if firmware_id not in self.firmware_database:
                return False, QCoreApplication.translate("FirmwareManager", "Firmware not found")
            
            firmware_info = self.firmware_database[firmware_id]
            
            if not firmware_info.file_path or not Path(firmware_info.file_path).exists():
                return False, QCoreApplication.translate("FirmwareManager", "Firmware file not found")
            
            # Calculate current checksum
            current_checksum = self._calculate_file_checksum(Path(firmware_info.file_path))
            
            if firmware_info.checksum and current_checksum != firmware_info.checksum:
                return False, QCoreApplication.translate("FirmwareManager", "Checksum mismatch. Expected: {}, Got: {}").format(firmware_info.checksum, current_checksum)
            
            # Check file size
            file_size = Path(firmware_info.file_path).stat().st_size
            if firmware_info.size and file_size != firmware_info.size:
                return False, QCoreApplication.translate("FirmwareManager", "File size mismatch. Expected: {}, Got: {}").format(firmware_info.size, file_size)
            
            return True, QCoreApplication.translate("FirmwareManager", "Firmware validation passed")
            
        except Exception as e:
            logger.error(f"Firmware validation failed: {e}")
            return False, QCoreApplication.translate("FirmwareManager", "Validation error: {}").format(str(e))
    
    def backup_device_firmware(self, device: Device, reason: str = "manual") -> str:
        """Backup current device firmware."""
        try:
            device_id = device.get_unique_id()
            
            # Read current firmware version
            current_firmware_version = device.firmware_version or "unknown"
            
            # Create backup info
            backup_info = FirmwareInfo(
                name=f"{device.board_type.value}_backup",
                version=current_firmware_version,
                source=FirmwareSource.LOCAL_FILE,
                board_type=device.board_type.value,
                compatible_devices=[device.board_type.value],
                release_date=datetime.now().isoformat()
            )
            
            # Create backup directory for device
            device_backup_dir = self.backups_dir / device_id
            device_backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}_{device.board_type.value}.bin"
            backup_path = device_backup_dir / backup_filename
            
            # For now, create a placeholder backup file
            # In a real implementation, this would read the actual firmware from the device
            backup_path.write_bytes(b"Firmware backup placeholder")
            
            # Create backup record
            backup = FirmwareBackup(
                device_id=device_id,
                firmware_info=backup_info,
                backup_path=str(backup_path),
                backup_date=datetime.now().isoformat(),
                backup_reason=reason,
                original_firmware=current_firmware_version
            )
            
            # Add to backups
            if device_id not in self.firmware_backups:
                self.firmware_backups[device_id] = []
            self.firmware_backups[device_id].append(backup)
            
            self._save_firmware_backups()
            
            logger.info(f"Created firmware backup for device {device_id}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to backup device firmware: {e}")
            raise
    
    def get_device_firmware_status(self, device: Device) -> FirmwareStatus:
        """Get firmware status for device."""
        try:
            device_id = device.get_unique_id()
            current_version = device.firmware_version or "unknown"
            
            # Find compatible firmware
            compatible_firmware = []
            for firmware_info in self.firmware_database.values():
                if (firmware_info.board_type == device.board_type.value or 
                    device.board_type.value in firmware_info.compatible_devices):
                    compatible_firmware.append(firmware_info)
            
            if not compatible_firmware:
                return FirmwareStatus.UNKNOWN
            
            # Find latest version
            latest_firmware = max(compatible_firmware, key=lambda f: f.version)
            
            if current_version == latest_firmware.version:
                return FirmwareStatus.LATEST
            elif current_version == "unknown":
                return FirmwareStatus.UNKNOWN
            else:
                return FirmwareStatus.OUTDATED
                
        except Exception as e:
            logger.error(f"Failed to get firmware status: {e}")
            return FirmwareStatus.UNKNOWN
    
    def get_available_updates(self, device: Device) -> List[FirmwareInfo]:
        """Get available firmware updates for device."""
        try:
            current_version = device.firmware_version or "unknown"
            
            # Find compatible firmware
            compatible_firmware = []
            for firmware_info in self.firmware_database.values():
                if (firmware_info.board_type == device.board_type.value or 
                    device.board_type.value in firmware_info.compatible_devices):
                    compatible_firmware.append(firmware_info)
            
            # Filter newer versions
            updates = []
            for firmware_info in compatible_firmware:
                if firmware_info.version != current_version:
                    updates.append(firmware_info)
            
            # Sort by version (newest first)
            updates.sort(key=lambda f: f.version, reverse=True)
            
            return updates
            
        except Exception as e:
            logger.error(f"Failed to get available updates: {e}")
            return []
    
    def get_device_backups(self, device: Device) -> List[FirmwareBackup]:
        """Get firmware backups for device."""
        device_id = device.get_unique_id()
        return self.firmware_backups.get(device_id, [])
    
    def _generate_firmware_id(self, firmware_info: FirmwareInfo) -> str:
        """Generate unique firmware ID."""
        # Use name, version, and source to generate ID
        id_string = f"{firmware_info.name}_{firmware_info.version}_{firmware_info.source.value}"
        return hashlib.md5(id_string.encode()).hexdigest()[:16]
    
    def _calculate_file_checksum(self, file_path: Path, algorithm: str = "sha256") -> str:
        """Calculate file checksum."""
        hash_func = hashlib.sha256() if algorithm == "sha256" else hashlib.md5()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    def _get_file_extension_from_url(self, url: str) -> str:
        """Extract file extension from URL."""
        try:
            # Remove query parameters
            url_path = url.split('?')[0]
            # Get extension
            return Path(url_path).suffix
        except:
            return ""
    
    def get_firmware_database(self) -> Dict[str, FirmwareInfo]:
        """Get firmware database."""
        return self.firmware_database.copy()
    
    def get_firmware_by_id(self, firmware_id: str) -> Optional[FirmwareInfo]:
        """Get firmware by ID."""
        return self.firmware_database.get(firmware_id)
    
    def delete_firmware(self, firmware_id: str):
        """Delete firmware from database."""
        if firmware_id in self.firmware_database:
            firmware_info = self.firmware_database[firmware_id]
            
            # Delete file if it exists
            if firmware_info.file_path and Path(firmware_info.file_path).exists():
                try:
                    Path(firmware_info.file_path).unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete firmware file: {e}")
            
            del self.firmware_database[firmware_id]
            self._save_firmware_database()
            logger.info(f"Deleted firmware: {firmware_id}")
    
    def cleanup_old_backups(self, days_to_keep: int = 30):
        """Clean up old firmware backups."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            for device_id, backups in self.firmware_backups.items():
                backups_to_remove = []
                
                for backup in backups:
                    backup_date = datetime.fromisoformat(backup.backup_date)
                    if backup_date < cutoff_date:
                        # Delete backup file
                        if Path(backup.backup_path).exists():
                            Path(backup.backup_path).unlink()
                        backups_to_remove.append(backup)
                
                # Remove old backups
                for backup in backups_to_remove:
                    backups.remove(backup)
                
                # Remove empty device entries
                if not backups:
                    del self.firmware_backups[device_id]
            
            self._save_firmware_backups()
            logger.info(f"Cleaned up backups older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
