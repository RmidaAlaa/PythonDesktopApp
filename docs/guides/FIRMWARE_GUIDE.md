# Firmware Flashing and Versioning Guide

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Supported Board Types](#supported-board-types)
4. [Installation and Setup](#installation-and-setup)
5. [Firmware Sources](#firmware-sources)
6. [Configuration](#configuration)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Features](#advanced-features)

## Overview

The AWG-Kumulus Desktop Application provides a comprehensive firmware management system that supports multiple board types and firmware sources. This guide covers all the ways to set up and use firmware flashing and versioning features.

### Key Features
- **Multi-platform Support**: Windows, macOS, and Linux
- **Multiple Board Types**: ESP32, ESP8266, STM32, Arduino
- **Various Firmware Sources**: Local files, GitHub releases, GitLab pipelines, URLs
- **Automatic Backup**: Creates firmware backups before updates
- **Version Management**: Track firmware versions and updates
- **Integrity Validation**: Checksum verification for downloaded firmware

## Prerequisites

### System Requirements
- Python 3.8 or higher
- Internet connection for downloading firmware and tools
- USB connection to target device
- Appropriate drivers for your board type

### Required Tools by Board Type

#### ESP32/ESP8266
```bash
pip install esptool
```

#### STM32
Choose one of the following:
- **STM32CubeProgrammer** (Recommended)
  - Download from: https://www.st.com/en/development-tools/stm32cubeprog.html
- **dfu-util** (Alternative)
  - Windows: Included with STM32CubeIDE
  - Linux: `sudo apt install dfu-util`
  - macOS: `brew install dfu-util`
- **OpenOCD** (Advanced)
  - Windows: Included with STM32CubeIDE
  - Linux: `sudo apt install openocd`
  - macOS: `brew install openocd`

#### Arduino
- **avrdude** (Usually included with Arduino IDE)
  - Windows: Included with Arduino IDE
  - Linux: `sudo apt install avrdude`
  - macOS: `brew install avrdude`

## Supported Board Types

The system supports the following board types:

| Board Type | Flash Tool | File Formats | Notes |
|------------|------------|--------------|-------|
| ESP32 | esptool | .bin, .elf | Most common IoT board |
| ESP8266 | esptool | .bin, .elf | Popular WiFi module |
| STM32 | STM32CubeProgrammer, dfu-util, OpenOCD | .bin, .elf | ARM Cortex-M microcontrollers |
| Arduino | avrdude | .hex, .bin | Classic Arduino boards |

## Installation and Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Platform-Specific Tools

#### Windows Setup
```powershell
# Install esptool for ESP32/ESP8266
pip install esptool

# Download STM32CubeProgrammer
# Visit: https://www.st.com/en/development-tools/stm32cubeprog.html
# Extract to: %APPDATA%\AWG-Kumulus\tools\STM32CubeProgrammer\

# Arduino IDE (includes avrdude)
# Download from: https://www.arduino.cc/en/software
```

#### Linux Setup
```bash
# Install esptool
pip install esptool

# Install STM32 tools
sudo apt update
sudo apt install dfu-util openocd

# Install Arduino tools
sudo apt install avrdude

# Install ARM toolchain (for STM32)
sudo apt install gcc-arm-none-eabi
```

#### macOS Setup
```bash
# Install esptool
pip install esptool

# Install STM32 tools via Homebrew
brew install dfu-util openocd

# Install Arduino tools
brew install avrdude

# Install ARM toolchain
brew install arm-none-eabi-gcc
```

### 3. Configure Application

The application will automatically create necessary directories and configuration files on first run:

```
Windows: %APPDATA%\AWG-Kumulus\
macOS: ~/Library/Application Support/AWG-Kumulus/
Linux: ~/.local/share/AWG-Kumulus/
```

## Firmware Sources

### 1. Local Files

Add firmware from local files on your system:

```python
from src.core.firmware_manager import FirmwareManager

fm = FirmwareManager()

# Add local firmware file
firmware_id = fm.add_firmware_from_file(
    file_path="/path/to/firmware.bin",
    name="My Firmware",
    version="1.0.0",
    board_type="ESP32",
    compatible_devices=["ESP32", "ESP32-S2"]
)
```

### 2. GitHub Releases

Add firmware from GitHub repository releases:

```python
# Add from latest release
firmware_id = fm.add_firmware_from_github(
    repo="owner/repository",
    board_type="ESP32"
)

# Add from specific release tag
firmware_id = fm.add_firmware_from_github(
    repo="owner/repository",
    release_tag="v1.2.3",
    asset_name="firmware.bin",
    board_type="ESP32"
)
```

### 3. GitLab Pipelines

Add firmware from GitLab CI/CD pipeline artifacts:

```python
# Add from latest successful pipeline
firmware_id = fm.add_firmware_from_gitlab(
    project_id="123456",
    board_type="STM32"
)

# Add from specific pipeline
firmware_id = fm.add_firmware_from_gitlab(
    project_id="123456",
    pipeline_id="789012",
    artifact_name="build",
    board_type="STM32"
)
```

### 4. URL Downloads

Add firmware from any accessible URL:

```python
firmware_id = fm.add_firmware_from_url(
    url="https://example.com/firmware.bin",
    name="Remote Firmware",
    version="2.0.0",
    board_type="Arduino",
    compatible_devices=["Arduino Uno", "Arduino Nano"]
)
```

## Configuration

### Configuration File Structure

The application uses a JSON configuration file located at:
- Windows: `%APPDATA%\AWG-Kumulus\config.json`
- macOS: `~/Library/Application Support/AWG-Kumulus/config.json`
- Linux: `~/.local/share/AWG-Kumulus/config.json`

```json
{
  "version": "1.0.0",
  "machine_types": {
    "Amphore": {
      "prefix": "AMP-",
      "length": 12
    },
    "BOKs": {
      "prefix": "BOK-",
      "length": 10
    },
    "WaterDispenser": {
      "prefix": "WD-",
      "length": 14
    }
  },
  "machine_type": "Amphore",
  "operator": {
    "name": "Operator Name",
    "email": "operator@example.com"
  },
  "onedrive": {
    "enabled": false,
    "folder_path": "",
    "user_folder": "",
    "sync_enabled": true,
    "auto_create_folders": true
  }
}
```

### Tool Path Configuration

The application automatically detects tools in the following locations:

```
Windows:
- %APPDATA%\AWG-Kumulus\tools\
- C:\Program Files\Arduino\
- C:\Program Files (x86)\Arduino\

Linux:
- /usr/bin/
- /usr/local/bin/
- ~/.local/bin/

macOS:
- /usr/local/bin/
- /opt/homebrew/bin/
- ~/.local/bin/
```

## Usage Examples

### 1. Basic Firmware Flashing

```python
from src.core.firmware_flasher import FirmwareFlasher
from src.core.device_detector import DeviceDetector

# Initialize components
flasher = FirmwareFlasher()
detector = DeviceDetector()

# Detect connected devices
devices = detector.detect_devices()

if devices:
    device = devices[0]
    
    # Flash firmware from local file
    success = flasher.flash_firmware(
        device=device,
        firmware_source="/path/to/firmware.bin"
    )
    
    if success:
        print("Firmware flashed successfully!")
    else:
        print("Firmware flashing failed!")
```

### 2. GitHub Release Flashing

```python
# Flash firmware from GitHub release
success = flasher.flash_from_github(
    device=device,
    repo="espressif/esp-idf",
    release_tag="v4.4",
    asset_name="esp32.bin"
)
```

### 3. GitLab Pipeline Flashing

```python
# Flash firmware from GitLab pipeline
success = flasher.flash_from_gitlab(
    device=device,
    project_id="123456",
    pipeline_id="789012",
    artifact_name="build"
)
```

### 4. URL Download Flashing

```python
# Flash firmware from URL
success = flasher.flash_from_url(
    device=device,
    url="https://example.com/firmware.bin",
    name="Remote Firmware",
    version="1.0.0"
)
```

### 5. Firmware Management

```python
from src.core.firmware_manager import FirmwareManager

fm = FirmwareManager()

# Get firmware status
status = flasher.get_device_firmware_status(device)
print(f"Current version: {status['current_version']}")
print(f"Status: {status['status']}")
print(f"Available updates: {status['available_updates']}")

# Get compatible firmware
compatible = flasher.get_compatible_firmware(device)
for firmware in compatible:
    print(f"- {firmware.name} v{firmware.version}")

# Backup current firmware
backup_path = fm.backup_device_firmware(device, "manual_backup")
print(f"Backup created: {backup_path}")

# Rollback to previous version
success = flasher.rollback_firmware(device, backup_index=0)
```

### 6. Progress Callback Example

```python
def progress_callback(message):
    print(f"Progress: {message}")

# Flash with progress updates
success = flasher.flash_firmware_by_id(
    device=device,
    firmware_id="firmware_id_here",
    progress_callback=progress_callback
)
```

## Troubleshooting

### Common Issues

#### 1. Tool Not Found
**Error**: `esptool not found` or similar

**Solutions**:
- Install the required tool: `pip install esptool`
- Check if the tool is in your PATH
- Verify the tool installation directory

#### 2. Device Not Detected
**Error**: No devices found

**Solutions**:
- Check USB connection
- Install appropriate drivers
- Verify device is in bootloader mode (if required)
- Check device permissions (Linux/macOS)

#### 3. Permission Denied
**Error**: Permission denied when accessing device

**Solutions**:
- Add user to dialout group (Linux): `sudo usermod -a -G dialout $USER`
- Run with appropriate permissions
- Check device permissions

#### 4. Firmware Download Failed
**Error**: Failed to download firmware

**Solutions**:
- Check internet connection
- Verify URL is accessible
- Check firewall settings
- Try alternative download method

#### 5. Checksum Validation Failed
**Error**: Firmware validation failed

**Solutions**:
- Re-download the firmware
- Check file integrity
- Verify firmware source

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Log Files

Log files are stored in:
- Windows: `%APPDATA%\AWG-Kumulus\logs\`
- macOS: `~/Library/Application Support/AWG-Kumulus/logs/`
- Linux: `~/.local/share/AWG-Kumulus/logs/`

## Advanced Features

### 1. Custom Firmware Sources

You can extend the firmware manager to support custom sources:

```python
class CustomFirmwareSource(FirmwareSource):
    CUSTOM_API = "custom_api"

# Add custom source handling
def add_firmware_from_custom_api(self, api_url: str, **kwargs):
    # Implementation for custom API
    pass
```

### 2. Firmware Signing and Verification

The system supports checksum verification:

```python
# Validate firmware integrity
is_valid, message = fm.validate_firmware(firmware_id)
if not is_valid:
    print(f"Validation failed: {message}")
```

### 3. Automatic Updates

Set up automatic firmware updates:

```python
# Check for updates
updates = fm.get_available_updates(device)
if updates:
    latest = updates[0]
    print(f"Update available: {latest.version}")
    
    # Auto-update if desired
    success = flasher.flash_firmware_by_id(device, latest.id)
```

### 4. Backup Management

```python
# Clean up old backups
fm.cleanup_old_backups(days_to_keep=30)

# Get backup history
backups = fm.get_device_backups(device)
for backup in backups:
    print(f"Backup: {backup.backup_date} - {backup.firmware_info.version}")
```

### 5. Batch Operations

```python
# Flash multiple devices
devices = detector.detect_devices()
for device in devices:
    if device.board_type == BoardType.ESP32:
        success = flasher.flash_firmware_by_id(device, firmware_id)
        print(f"Device {device.port}: {'Success' if success else 'Failed'}")
```

## Best Practices

### 1. Always Backup Before Flashing
```python
# Create backup before any firmware update
backup_path = fm.backup_device_firmware(device, "before_update")
```

### 2. Validate Firmware Before Flashing
```python
# Validate firmware integrity
is_valid, message = fm.validate_firmware(firmware_id)
if not is_valid:
    print(f"Skipping invalid firmware: {message}")
    return False
```

### 3. Use Progress Callbacks
```python
# Provide user feedback during long operations
def progress_callback(message):
    print(f"Progress: {message}")
    # Update UI if applicable
```

### 4. Handle Errors Gracefully
```python
try:
    success = flasher.flash_firmware(device, firmware_source)
    if not success:
        # Restore backup if available
        flasher.rollback_firmware(device)
except Exception as e:
    logger.error(f"Firmware operation failed: {e}")
    # Handle error appropriately
```

### 5. Regular Cleanup
```python
# Clean up old files periodically
fm.cleanup_old_backups(days_to_keep=30)
```

## Support and Resources

### Documentation
- [ESP32 Programming Guide](https://docs.espressif.com/projects/esp-idf/en/latest/)
- [STM32 Development Guide](https://www.st.com/en/development-tools/stm32cubeprog.html)
- [Arduino Reference](https://www.arduino.cc/reference/)

### Community
- [ESP32 Forum](https://esp32.com/)
- [STM32 Community](https://community.st.com/)
- [Arduino Forum](https://forum.arduino.cc/)

### Tools and Downloads
- [esptool](https://github.com/espressif/esptool)
- [STM32CubeProgrammer](https://www.st.com/en/development-tools/stm32cubeprog.html)
- [dfu-util](http://dfu-util.sourceforge.net/)
- [avrdude](https://www.nongnu.org/avrdude/)

---

This guide covers all the essential aspects of firmware flashing and versioning in the AWG-Kumulus Desktop Application. For additional support or feature requests, please refer to the project documentation or contact the development team.
