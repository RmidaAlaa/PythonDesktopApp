"""Configuration and settings management."""

import json
import platform
from pathlib import Path


class Config:
    """Configuration manager for the application."""
    
    APP_NAME = "AWG-Kumulus"
    
    # Platform-specific paths
    if platform.system() == "Windows":
        APPDATA_DIR = Path.home() / "AppData" / "Roaming" / APP_NAME
        TOOLS_DIR = APPDATA_DIR / "tools"
    elif platform.system() == "Darwin":  # macOS
        APPDATA_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
        TOOLS_DIR = APPDATA_DIR / "tools"
    else:  # Linux
        APPDATA_DIR = Path.home() / ".local" / "share" / APP_NAME
        TOOLS_DIR = APPDATA_DIR / "tools"
    
    CONFIG_FILE = APPDATA_DIR / "config.json"
    LOGS_DIR = APPDATA_DIR / "logs"
    
    # Helper binaries metadata
    HELPER_TOOLS = {
        "esptool": {
            "url": "https://github.com/espressif/esptool/archive/refs/heads/master.zip",
            "platform": "all",
            "checksums": {
                "windows": None,
                "linux": None,
                "darwin": None
            }
        },
        "dfu-util": {
            "url": "https://sourceforge.net/projects/dfu-util/files/latest/download",
            "platform": "all",
            "checksums": {}
        },
        "STM32CubeProgrammer": {
            "url": "https://www.st.com/en/development-tools/stm32cubeprog.html",
            "platform": "all",
            "checksums": {}
        },
        "avrdude": {
            "url": "https://sourceforge.net/projects/winavr/files/latest/download",
            "platform": "all",
            "checksums": {}
        }
    }
    
    MACHINE_TYPES = {
        "Amphore": {"prefix": "AMP-", "length": 12},
        "BOKs": {"prefix": "BOK-", "length": 10},
        "WaterDispenser": {"prefix": "WD-", "length": 14}
    }
    
    DEFAULT_CONFIG = {
        "version": "1.0.0",
        "smtp": {
            "host": "",
            "port": 587,
            "tls": True,
            "username": "",
            "password": ""
        },
        "recipients": [],
        "machine_types": MACHINE_TYPES.copy(),  # Include default machine types
        "machine_type": "Amphore",
        "operator": {
            "name": "",
            "email": ""
        },
        "onedrive": {
            "enabled": False,
            "folder_path": "",
            "user_folder": "",
            "sync_enabled": True,
            "auto_create_folders": True
        }
    }
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load_config(cls):
        """Load configuration from file."""
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                for key, value in cls.DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        return cls.DEFAULT_CONFIG.copy()
    
    @classmethod
    def save_config(cls, config):
        """Save configuration to file."""
        with open(cls.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    @classmethod
    def get_tool_path(cls, tool_name):
        """Get the path to a helper tool."""
        return cls.TOOLS_DIR / tool_name
    
    @classmethod
    def is_first_run(cls):
        """Check if this is the first run."""
        return not cls.CONFIG_FILE.exists()
    
    @classmethod
    def get_app_data_dir(cls):
        """Get the application data directory."""
        return cls.APPDATA_DIR
    
    @classmethod
    def get_machine_types(cls, config=None):
        """Get machine types from config."""
        if config is None:
            config = cls.load_config()
        return config.get('machine_types', cls.MACHINE_TYPES.copy())
    
    @classmethod
    def add_machine_type(cls, config, name, prefix, length):
        """Add a new machine type to config."""
        if 'machine_types' not in config:
            config['machine_types'] = cls.MACHINE_TYPES.copy()
        
        config['machine_types'][name] = {
            "prefix": prefix,
            "length": length
        }
        return config
    
    @classmethod
    def update_machine_type(cls, config, old_name, new_name, prefix, length):
        """Update an existing machine type."""
        if 'machine_types' not in config:
            config['machine_types'] = cls.MACHINE_TYPES.copy()
        
        # Remove old entry if name changed
        if old_name != new_name and old_name in config['machine_types']:
            del config['machine_types'][old_name]
        
        # Add/update with new data
        config['machine_types'][new_name] = {
            "prefix": prefix,
            "length": length
        }
        return config
    
    @classmethod
    def delete_machine_type(cls, config, name):
        """Delete a machine type from config."""
        if 'machine_types' in config and name in config['machine_types']:
            del config['machine_types'][name]
        return config
    
    @classmethod
    def validate_machine_id(cls, machine_id, machine_type_config):
        """Validate machine ID format."""
        prefix = machine_type_config.get('prefix', '')
        length = machine_type_config.get('length', 0)
        
        if not machine_id.startswith(prefix):
            return False, f"Machine ID must start with '{prefix}'"
        
        if len(machine_id) != length:
            return False, f"Machine ID must be {length} characters long"
        
        return True, "Valid"

