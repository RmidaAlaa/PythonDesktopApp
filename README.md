# AWG Kumulus Device Manager

Cross-platform Python desktop application for managing embedded boards (STM32, ESP32, Arduino, etc.).

## Features

- **Cross-Platform**: Works on Windows, Linux, and macOS (MacBook)
- **Device Detection**: Automatically detects STM32 boards connected via USB
- **Board Information**: Reads chip UIDs, manufacturer info, firmware versions
- **Excel Reports**: Generates professional `.xlsx` reports with metadata and device information
- **Email Integration**: Securely sends reports via SMTP (credentials stored in OS keychain)
- **Firmware Flashing**: Flash firmware from local files or remote sources (GitLab, OneDrive, REST API)
- **First-Run Bootstrap**: Automatically downloads required helper binaries on first launch
- **Secure Storage**: Uses `keyring` for secure credential management (Windows Credential Manager / macOS Keychain / Linux Secret Service)
- **Footer Info**: Displays your local timezone and approximate location (city, country)
- **Offline Email Queuing**: Automatically queues emails when offline and sends them when connection is restored
- **Smart Updates**: Background update checks with notification badges and one-click direct installation
- **Single Executable**: Distributed as a standalone .exe file with no external dependencies

## Requirements

- Python 3.11 or higher
- USB port for connecting devices
- Internet connection (for first-run setup and downloading helper binaries)

## Installation

### Development

1. Clone the repository:
```bash
git clone <repository-url>
cd DesktopApp
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
- Windows: `venv\Scripts\activate`
- Linux/macOS: `source venv/bin/activate`

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run the application:
```bash
python main.py
```

## Building Executables

### Windows (.exe)

```bash
pyinstaller --clean app.spec
```

The executable will be in `dist/AWGKumulusDeviceManager.exe`. This is a single standalone file that can be moved anywhere.

### Linux (AppImage)

```bash
pyinstaller --name="AWG-Kumulus-Device-Manager" --windowed --onedir main.py
```

Then package as AppImage (requires additional tools).

### macOS (.app)

```bash
pyinstaller --name="AWG-Kumulus-Device-Manager" --windowed --onedir main.py
```

The `.app` bundle will be in `dist/AWG-Kumulus-Device-Manager.app`

## Project Structure

```
DesktopApp/
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── machineTypes.json       # Machine type configurations
├── src/
│   ├── __init__.py
│   ├── core/               # Core functionality
│   │   ├── config.py       # Configuration management
│   │   ├── logger.py       # Logging setup
│   │   ├── bootstrap.py    # First-run setup
│   │   ├── device_detector.py  # Device detection
│   │   ├── report_generator.py # Excel report generation
│   │   ├── email_sender.py     # Email functionality
│   │   └── firmware_flasher.py # Firmware flashing
│   └── gui/                # GUI components
│       ├── main_window.py  # Main application window
│       └── ...
├── pyproject.toml          # Project metadata
└── README.md              # This file
```

## Usage

### First Run

1. Launch the application
2. The app will automatically download required helper binaries (esptool, dfu-util, etc.)
3. Click "Refresh Devices" to scan for connected boards

### Footer Information

- The status bar footer shows your local timezone and approximate location.
- Location is detected using public IP geolocation (ipapi.co) when available; if offline, it falls back to unknown.
- No personal data is stored; results are displayed only in the UI.

### Detecting Devices

- Click the "🔄 Refresh Devices" button to scan for connected boards
- Detected devices will appear in the table with:
  - Port (e.g., COM3, /dev/ttyUSB0)
  - Board type (STM32, ESP32, etc.)
  - VID:PID (Vendor/Product ID)
  - Connection status

### Generating Reports

1. Enter operator name and email
2. Select machine type (Amphore, BOKs, Water Dispenser)
3. Enter machine ID (validated against prefix and length)
4. Click "📊 Generate Excel Report"

The report will be saved in the application data directory.

### Sending Emails

1. Configure SMTP settings in the Settings dialog
2. Credentials are stored securely using the OS keychain
3. Click "📧 Send Email" to send the latest report

**Offline Mode:** If you are offline, the email will be queued automatically. It will be sent as soon as the internet connection is restored or when you restart the app. A confirmation popup will warn you if you try to exit with unsent emails.

### Application Updates

1. The app automatically checks for updates in the background on startup.
2. If an update is available, a red notification badge (e.g., "1") appears on the update button.
3. Click the update button to view details and click "Install Update".
4. The app will download the installer, run it, and restart.

### Flashing Firmware

1. Select a device from the device list
2. Click "⚡ Flash Firmware"
3. Choose firmware source (local file, URL, GitLab, etc.)
4. Monitor progress in the log area

## Machine Types Configuration

```json
{
  "Amphore": {"prefix": "AMP-", "length": 12},
  "BOKs": {"prefix": "BOK-", "length": 10},
  "WaterDispenser": {"prefix": "WD-", "length": 14}
}
```

You can customize these in `machineTypes.json`.

## Helper Tools

The application uses the following helper binaries (downloaded automatically):

- **dfu-util**: For STM32 DFU mode flashing
- **STM32CubeProgrammer**: For STM32 flashing

These are stored in platform-specific directories:
- Windows: `%APPDATA%/AWG-Kumulus/tools`
- Linux: `~/.local/share/awg-kumulus/tools`
- macOS: `~/Library/Application Support/AWG-Kumulus/tools`

## Security

- All network connections use HTTPS
- Credentials are stored securely using the OS keychain (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- No sensitive data is stored in plain text files

## Troubleshooting

### Devices Not Detected

- Ensure the device is connected via USB
- Check that the appropriate drivers are installed
- On Linux, you may need to add your user to the `dialout` group:
  ```bash
  sudo usermod -a -G dialout $USER
  ```

### Firmware Flashing Fails

- Ensure the device is in bootloader mode
- Check that the correct helper binary is installed
- Verify the firmware file is valid
- Check the logs in the application data directory

### Email Not Sending

- Verify SMTP settings are correct
- Check that credentials are stored in the keyring
- Ensure the network connection is active
- Check firewall settings

## Development

### Running Tests

```bash
pytest
```

### Code Style

The project follows PEP 8 style guidelines. Consider using a formatter like `black`:

```bash
black src/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Specify your license here]

## Support

For issues and questions, please open an issue on the repository.

## Changelog

### Version 1.0.0
- Initial release
- Support for Windows, Linux, and macOS
- Device detection for STM32 boards
- Excel report generation
- Email integration with SMTP
- Firmware flashing for STM32 boards
- First-run bootstrap for helper binaries
- Secure credential storage with keyring

