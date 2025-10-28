# AWG Kumulus Device Manager - Architecture

## Overview

The AWG Kumulus Device Manager is a cross-platform Python desktop application built with PySide6 for managing embedded boards. It provides device detection, firmware flashing, and professional reporting capabilities.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Application                         │
│                        (main.py)                            │
└────────────────────────┬────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
    ┌───────▼─────────┐      ┌────────▼────────┐
    │  GUI Layer      │      │  Core Modules   │
    │  (PySide6)      │◄────►│  (Business      │
    │                 │      │   Logic)        │
    └───────┬─────────┘      └────────┬────────┘
            │                         │
    ┌───────▼─────────┐      ┌────────▼────────┐
    │ MainWindow      │      │ DeviceDetector  │
    │   - UI Layout   │      │ - STM32         │
    │   - Controls    │      │ - ESP32         │
    │   - Logs        │      │ - Arduino       │
    └─────────────────┘      └────────┬────────┘
                                       │
            ┌──────────────────────────┼──────────────────────┐
            │                          │                      │
    ┌───────▼────────┐      ┌──────────▼──────┐    ┌──────────▼────────┐
    │ Report Gen     │      │ Firmware Flasher│    │  Email Sender     │
    │  - Excel       │      │  - STM32        │    │  - SMTP           │
    │  - Metadata    │      │  - ESP32       │    │  - Keyring        │
    └───────────────┘      └─────────────────┘    └───────────────────┘
```

## Directory Structure

```
DesktopApp/
├── main.py                      # Entry point
├── requirements.txt              # Dependencies
├── pyproject.toml               # Project metadata
├── setup.py                     # Setuptools config
├── machineTypes.json            # Machine type definitions
├── build_windows.spec           # PyInstaller spec (Windows)
├── build_linux.spec             # PyInstaller spec (Linux)
├── build_macos.spec             # PyInstaller spec (macOS)
├── build.py                     # Build script
├── README.md                    # Main documentation
├── QUICKSTART.md                # Quick start guide
├── BUILD.md                     # Build instructions
├── ARCHITECTURE.md              # This file
│
├── src/                         # Source code
│   ├── __init__.py
│   ├── core/                    # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py            # Configuration management
│   │   ├── logger.py            # Logging setup
│   │   ├── bootstrap.py         # First-run setup
│   │   ├── device_detector.py   # Device detection
│   │   ├── report_generator.py  # Excel report generation
│   │   ├── email_sender.py      # Email functionality
│   │   └── firmware_flasher.py  # Firmware flashing
│   │
│   └── gui/                     # GUI components
│       ├── __init__.py
│       └── main_window.py       # Main UI window
│
└── tests/                       # Test suite
    ├── __init__.py
    └── test_device_detector.py  # Device detection tests
```

## Core Modules

### config.py
- Handles configuration loading/saving
- Manages platform-specific paths (Windows, Linux, macOS)
- Defines machine types and helper tool metadata
- Provides configuration defaults

### logger.py
- Sets up Python logging
- Console and file handlers
- Rotating log files (10MB max, 5 backups)
- Different log levels for dev/prod

### bootstrap.py
- First-run setup
- Checks for required Python packages
- Downloads helper binaries (esptool, dfu-util, etc.)
- Platform-specific tool detection
- Returns warnings if setup incomplete

### device_detector.py
- Scans for connected USB devices
- Identifies board type (STM32, ESP32, Arduino)
- Reads device information (VID:PID, serial, manufacturer)
- Provides device enumeration and filtering
- Supports multiple device types

### report_generator.py
- Creates Excel reports using openpyxl
- Generates metadata sheet (timestamp, operator, PC info)
- Generates devices sheet (machine info, board details)
- Professional formatting (borders, colors, auto-sizing)

### email_sender.py
- SMTP email functionality
- Secure credential storage with keyring
- Supports attachments
- Progress callback for UI updates

### firmware_flasher.py
- Flashes firmware to connected boards
- Supports multiple sources (local file, URL, GitLab)
- Platform-specific flashers:
  - ESP32: esptool.py
  - STM32: dfu-util / STM32CubeProgrammer
  - Arduino: avrdude
- Progress reporting and verification

## GUI Components

### main_window.py
- Main application window
- Splitter layout (devices on left, controls on right)
- Device table (port, type, status)
- Operator info form
- Machine type/ID inputs with validation
- Action buttons (Generate Report, Send Email, Flash Firmware)
- Progress bar and log area
- Settings integration

## Data Flow

1. **Device Detection**: `device_detector.py` scans USB ports → returns list of `Device` objects
2. **UI Update**: Devices displayed in table
3. **User Input**: Operator selects device, enters info, chooses machine type
4. **Report Generation**: `report_generator.py` creates Excel file
5. **Email**: `email_sender.py` sends report (credentials from keyring)
6. **Firmware Flash**: `firmware_flasher.py` flashes firmware to device

## Security

- **Credential Storage**: Uses OS keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- **HTTPS Only**: All network requests use HTTPS
- **No Hardcoded Secrets**: All sensitive data stored securely
- **Privacy Notice**: Shown on first run

## Platform Support

- **Windows**: `.exe` via PyInstaller, config in `%APPDATA%`
- **Linux**: AppImage or `.deb`, config in `~/.local/share`
- **macOS**: `.app` bundle, config in `~/Library/Application Support`

## Extensibility

- New board types: Add to `BOARD_VIDPIDS` in `device_detector.py`
- New machine types: Add to `MACHINE_TYPES` in `config.py` or `machineTypes.json`
- Custom flashers: Add methods to `firmware_flasher.py`
- UI components: Extend `main_window.py` with new dialogs

## Testing

- Unit tests for device detection
- Mock serial ports for testing
- Integration tests for report generation
- CI/CD for all platforms

## Deployment

1. Build executables with PyInstaller
2. Test on target platforms
3. Package with platform-specific tools (NSIS, AppImage, DMG)
4. Distribute to users
5. Updates via version checking

## Future Enhancements

- Firmware version checking
- Auto-update mechanism
- Remote device configuration
- Batch operations (multiple devices)
- Plugin system for custom board support
- Export to other formats (PDF, CSV)

