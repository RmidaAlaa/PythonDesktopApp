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
        url = tool_info.get("url")
        if not url:
            logger.error(f"No URL for tool: {tool_name}")
            return False

        tool_path = self.config.get_tool_path(tool_name)
        
        try:
            logger.info(f"Downloading {tool_name} from {url}...")
            
            # Create tools directory
            tool_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download to temp file
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            temp_file = tool_path.parent / f"{tool_name}_temp.zip"
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Check if it's a zip file
            if zipfile.is_zipfile(temp_file):
                logger.info(f"Extracting {tool_name}...")
                with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                    # Extract to a temp dir first to avoid clutter
                    extract_dir = tool_path.parent / f"{tool_name}_extract"
                    zip_ref.extractall(extract_dir)
                    
                    # Move contents to final tool_path
                    # If tool_path exists (as a dir), clear it
                    if tool_path.exists():
                        shutil.rmtree(tool_path)
                    
                    # If extraction created a single folder, move that folder
                    # Otherwise move the whole extract_dir
                    items = list(extract_dir.iterdir())
                    if len(items) == 1 and items[0].is_dir():
                        shutil.move(str(items[0]), str(tool_path))
                    else:
                        shutil.move(str(extract_dir), str(tool_path))
                        
                    # Cleanup extract dir if it still exists
                    if extract_dir.exists():
                        shutil.rmtree(extract_dir)
            else:
                # Assume it's a standalone binary (or invalid)
                # If the target is a directory, this is awkward.
                # We'll create the directory and move the file inside.
                tool_path.mkdir(parents=True, exist_ok=True)
                final_file = tool_path / url.split('/')[-1]
                shutil.move(str(temp_file), str(final_file))
                
                # Make executable on Linux/Mac
                if platform.system() != "Windows":
                    final_file.chmod(0o755)

            # Cleanup temp file
            if temp_file.exists():
                temp_file.unlink()
            
            logger.info(f"Downloaded {tool_name} successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {tool_name}: {e}")
            # Cleanup
            try:
                if 'temp_file' in locals() and temp_file.exists():
                    temp_file.unlink()
            except:
                pass
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
    
    def check_firmware_files(self) -> bool:
        """Check and download necessary firmware files."""
        # Create GetMachineID folder in workspace
        target_dir = self.config.WORKSPACE_DIR / "GetMachineID"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        firmware_path = target_dir / "GetMachineUid.bin"
        if firmware_path.exists() and firmware_path.stat().st_size > 0:
            return True
            
        logger.info("Downloading GetMachineUid.bin...")
        try:
            url = self.config.GET_MACHINE_UID_URL
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Check for HTML content
            content_type = response.headers.get('Content-Type', '').lower()
            if 'html' in content_type:
                logger.error(f"Download failed: URL returned HTML instead of binary (Content-Type: {content_type})")
                return False
            
            # Save to temporary file first
            temp_path = firmware_path.with_suffix(".tmp")
            first_chunk_checked = False
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not first_chunk_checked:
                        if b'<!DOCTYPE html>' in chunk or b'<html' in chunk:
                            logger.error("Download failed: Content appears to be HTML")
                            return False
                        first_chunk_checked = True
                    f.write(chunk)
            
            # Rename to final file
            if temp_path.exists():
                temp_path.replace(firmware_path)
            
            logger.info("Downloaded GetMachineUid.bin successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to download GetMachineUid.bin: {e}")
            return False

    def install_missing_packages(self, missing: List[str]) -> bool:
        """Install missing Python packages using pip."""
        if not missing:
            return True
            
        logger.info(f"Installing missing packages: {', '.join(missing)}")
        try:
            # Construct pip install command
            cmd = [sys.executable, "-m", "pip", "install"] + missing
            
            # Run pip
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Packages installed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install packages: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error during package installation: {e}")
            return False

    def run_first_run_setup(self) -> Tuple[bool, List[str]]:
        """Run first-run setup and return success status and any warnings."""
        warnings = []
        
        # Check Python packages
        missing_packages = self.check_python_packages()
        if missing_packages:
            logger.info(f"Found missing packages: {missing_packages}")
            # Try to install them automatically
            if self.install_missing_packages(missing_packages):
                # Re-check to confirm
                still_missing = self.check_python_packages()
                if still_missing:
                    warnings.append(f"Failed to install: {', '.join(still_missing)}")
            else:
                warnings.append(f"Missing Python packages: {', '.join(missing_packages)}")
        
        # Check platform tools
        if not self.setup_platform_tools():
            warnings.append("Some platform tools may not be available")
        
        # For now, just ensure directories exist
        self.config.ensure_directories()
        
        return True, warnings

