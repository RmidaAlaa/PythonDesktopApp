"""Configuration and settings management."""

import json
import platform
import shutil
from pathlib import Path


class Config:
    """Configuration manager for the application."""
    
    APP_NAME = "AWG-Kumulus"
    
    # Platform-specific paths
    if platform.system() == "Windows":
        APPDATA_DIR = Path.home() / "AppData" / "Roaming" / APP_NAME
        WORKSPACE_DIR = Path.home() / "Documents" / "AWG-Kumulus-Workspace"
        TOOLS_DIR = APPDATA_DIR / "tools"
    elif platform.system() == "Darwin":  # macOS
        APPDATA_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
        WORKSPACE_DIR = Path.home() / "Documents" / "AWG-Kumulus-Workspace"
        TOOLS_DIR = APPDATA_DIR / "tools"
    else:  # Linux
        APPDATA_DIR = Path.home() / ".local" / "share" / APP_NAME
        WORKSPACE_DIR = Path.home() / "Documents" / "AWG-Kumulus-Workspace"
        TOOLS_DIR = APPDATA_DIR / "tools"
    
    CONFIG_FILE = APPDATA_DIR / "config.json"
    LOGS_DIR = WORKSPACE_DIR / "logs"
    
    # Firmware URLs
    GET_MACHINE_UID_URL = "https://raw.githubusercontent.com/RmidaAlaa/PythonDesktopApp/main/BinaryFiles/GetMachineID/GetMachineUid.bin"

    # Helper binaries metadata
    HELPER_TOOLS = {
        "dfu-util": {
            # Windows release from official releases
            "url": "http://dfu-util.sourceforge.net/releases/dfu-util-0.11-binaries.tar.xz",
            "platform": "all",
            "checksums": {}
        },
        "STM32CubeProgrammer": {
            # Note: Requires login/acceptance of license. Using landing page.
            # Users should install this manually if not found.
            "url": "https://www.st.com/en/development-tools/stm32cubeprog.html",
            "platform": "all",
            "checksums": {}
        },
        "avrdude": {
            # Windows binary release
            "url": "https://github.com/avrdudes/avrdude/releases/download/v7.2/avrdude-v7.2-windows-x64.zip",
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
        "admin_password": "AWG",
        "auto_flash": {
            "enabled": False,
            "firmware_path": "",
            "board_types": ["STM32"],
            "erase": True,
            "verify": True
        },
        "smtp": {
            "host": "",
            "port": 587,
            "tls": True,
            "username": "",
            "password": ""
        },
        "azure": {
            "enabled": True,
            "client_id": "5cc56638-0cbd-4157-8048-a45be46796e6",
            "client_secret": "",
            "tenant_id": "0ec61e2c-d103-4eba-9c26-0f87efc69a51",
            "sender_email": "aabengandia@kumuluswater.com"
        },
        "recipients": [],
        "machine_types": MACHINE_TYPES.copy(),  # Include default machine types
        "machine_type": "Amphore",
        "machine_id": "",
        "machine_id_suffix": "",
        "client_name": "",
        "operator": {
            "name": "",
            "email": ""
        },
        "tour_seen": False,
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
        cls.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load_config(cls):
        """Load configuration from file."""
        try:
            if cls.CONFIG_FILE.exists():
                text = cls.CONFIG_FILE.read_text(encoding="utf-8")
                if not text.strip():
                    # Empty file; initialize with defaults
                    default_cfg = cls.DEFAULT_CONFIG.copy()
                    cls.save_config(default_cfg)
                    return default_cfg
                with open(cls.CONFIG_FILE, 'r', encoding="utf-8") as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in cls.DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    return config
            # No config file; return defaults and create file
            cfg = cls.DEFAULT_CONFIG.copy()
            try:
                cls.ensure_directories()
                cls.save_config(cfg)
            except Exception:
                pass
            return cfg
        except Exception:
            # Fallback: corrupted or unreadable config; reset to defaults
            cfg = cls.DEFAULT_CONFIG.copy()
            try:
                cls.save_config(cfg)
            except Exception:
                pass
            return cfg
    
    @classmethod
    def save_config(cls, config):
        """Save configuration to file."""
        with open(cls.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    @classmethod
    def get_tool_path(cls, tool_name):
        """Get the path to a helper tool directory."""
        return cls.TOOLS_DIR / tool_name

    @classmethod
    def get_tool_executable(cls, tool_name, exe_name):
        """Get the path to a helper tool executable, searching in tools dir, system path, and common install locations."""
        # 1. Check in TOOLS_DIR
        tool_dir = cls.get_tool_path(tool_name)
        exe_path = tool_dir / exe_name
        if exe_path.exists():
            return str(exe_path)
            
        # 2. Check in system PATH
        system_path = shutil.which(exe_name)
        if system_path:
            return system_path
            
        # 3. Check specific tool name without extension
        base_name = Path(exe_name).stem
        system_path_base = shutil.which(base_name)
        if system_path_base:
            return system_path_base

        # 4. Check common installation paths (Windows)
        if platform.system() == "Windows":
            common_paths = [
                Path(r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin") / exe_name,
                Path(r"C:\Program Files (x86)\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin") / exe_name,
                Path(r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe"),
                Path(r"C:\ST\STM32CubeProgrammer\bin") / exe_name
            ]
            for p in common_paths:
                if p.exists():
                    return str(p)
            
        # 5. Fallback to expected path
        return str(exe_path)

    
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

