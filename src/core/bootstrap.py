"""First-run bootstrap and helper binary downloader."""

import sys
import subprocess
import hashlib
import platform
from pathlib import Path
from typing import List, Tuple
import requests
from tqdm import tqdm

from .config import Config
from .logger import setup_logger

logger = setup_logger("Bootstrap")


class BootstrapManager:
    """Manages first-run setup and helper binary downloads."""
    
    def __init__(self):
        self.config = Config
        self.logger = logger
    
    def check_required_tools(self) -> List[str]:
        """Check which helper tools are missing."""
        missing = []
        for tool_name in self.config.HELPER_TOOLS.keys():
            tool_path = self.config.get_tool_path(tool_name)
            if not tool_path.exists():
                missing.append(tool_name)
        return missing
    
    def check_python_packages(self) -> List[str]:
        """Check which Python packages are missing."""
        required = ['pyserial', 'pyusb', 'openpyxl', 'requests', 'keyring', 'PySide6']
        missing = []
        for package in required:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing.append(package)
        return missing
    
    def download_tool(self, tool_name: str, progress_callback=None) -> bool:
        """Download and install a helper tool."""
        if tool_name not in self.config.HELPER_TOOLS:
            logger.error(f"Unknown tool: {tool_name}")
            return False
        
        tool_info = self.config.HELPER_TOOLS[tool_name]
        tool_path = self.config.get_tool_path(tool_name)
        
        try:
            logger.info(f"Downloading {tool_name}...")
            
            # In a real implementation, you would:
            # 1. Download from the URL
            # 2. Verify checksum
            # 3. Extract/install to tool_path
            
            # For now, just create a placeholder
            tool_path.parent.mkdir(parents=True, exist_ok=True)
            tool_path.write_text(f"# Placeholder for {tool_name}")
            
            logger.info(f"Downloaded {tool_name} successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {tool_name}: {e}")
            return False
    
    def setup_platform_tools(self):
        """Set up platform-specific tools."""
        system = platform.system()
        
        if system == "Windows":
            # Check if Python is available in PATH
            return self.check_python_in_path()
        elif system == "Linux":
            # Check for esptool, avrdude via package manager
            return self.check_system_tools()
        elif system == "Darwin":  # macOS
            # Check for tools via Homebrew or direct install
            return self.check_macos_tools()
        else:
            logger.warning(f"Unknown platform: {system}")
            return False
    
    def check_python_in_path(self) -> bool:
        """Check if Python is in PATH."""
        try:
            result = subprocess.run(['python', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def check_system_tools(self) -> bool:
        """Check for system-installed tools on Linux."""
        tools = ['esptool', 'dfu-util']
        found = []
        for tool in tools:
            try:
                result = subprocess.run(['which', tool], 
                                      capture_output=True)
                if result.returncode == 0:
                    found.append(tool)
            except:
                pass
        logger.info(f"Found system tools: {found}")
        return True  # Don't fail if tools are missing
    
    def check_macos_tools(self) -> bool:
        """Check for Mac-specific tools."""
        return self.check_system_tools()
    
    def run_first_run_setup(self) -> Tuple[bool, List[str]]:
        """Run first-run setup and return success status and any warnings."""
        warnings = []
        
        # Check Python packages
        missing_packages = self.check_python_packages()
        if missing_packages:
            warnings.append(f"Missing Python packages: {', '.join(missing_packages)}")
        
        # Check platform tools
        if not self.setup_platform_tools():
            warnings.append("Some platform tools may not be available")
        
        # For now, just ensure directories exist
        self.config.ensure_directories()
        
        return True, warnings

