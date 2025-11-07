# Quick Start Guide

## Getting Started in 5 Minutes

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python main.py
```

### 3. First Run Setup

- The application will automatically set up necessary directories
- If helper binaries are needed, you'll be prompted to download them

### 4. Connect a Device

- Connect an embedded board (STM32, ESP32, Arduino) via USB
- Click "🔄 Refresh Devices" to detect it

### 5. Generate a Report

1. Enter your name and email
2. Select machine type (Amphore, BOKs, Water Dispenser)
3. Enter machine ID (e.g., "AMP-12345678")
4. Click "📊 Generate Excel Report"

## Common Tasks

### Refresh Device List

Click the "🔄 Refresh Devices" button to scan for newly connected boards.

### Configure Email (for sending reports)

1. Open Settings (TODO: implement settings dialog)
2. Enter SMTP configuration:
   - Host: `smtp.gmail.com`
   - Port: `587`
   - TLS: Enabled
   - Username: Your email
   - Password: Stored securely in keyring
3. Add recipient email addresses

### Flash Firmware

1. Select a device from the list
2. Click "⚡ Flash Firmware"
3. Choose firmware source:
   - Local file (`.bin`, `.hex`, `.elf`)
   - URL (HTTPS)
   - GitLab repository
4. Monitor progress in the log area

## Troubleshooting

### "No devices detected"

- Ensure device is connected via USB
- Install appropriate drivers
- Check device manager (Windows) or `lsusb` (Linux)

### "Import errors"

- Ensure virtual environment is activated
- Run: `pip install -r requirements.txt`

### "Permission denied" (Linux)

```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

## Next Steps

- Read the [Full README](README.md) for detailed information
- Check [Build Instructions](BUILD.md) to create executables
- Review the code to understand the architecture

## Footer Information

- The status bar footer shows your local timezone and approximate location.
- Location is detected using public IP geolocation (ipapi.co) when available; if offline, it falls back to unknown.
- No personal data is stored; results are displayed only in the UI.

