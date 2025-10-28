# Building AWG Kumulus Device Manager

This document explains how to build the application for different platforms.

## Prerequisites

- Python 3.11 or higher
- All dependencies installed (`pip install -r requirements.txt`)
- PyInstaller installed (`pip install pyinstaller`)

## Building Executables

### Windows

1. Build the executable:
```bash
pyinstaller build_windows.spec
```

2. The executable will be in `dist/AWG-Kumulus-Device-Manager.exe`

3. To create an installer with NSIS (optional):
   - Install NSIS
   - Create an NSIS script for packaging the executable

### Linux

1. Build the executable:
```bash
pyinstaller build_linux.spec
```

2. The application will be in `dist/AWG-Kumulus-Device-Manager/`

3. To create an AppImage:
   - Use `linuxdeploy` or similar tools
   - Or create a `.deb` package with `dpkg-buildpackage`

### macOS

1. Build the application bundle:
```bash
pyinstaller build_macos.spec
```

2. The `.app` bundle will be in `dist/AWG-Kumulus-Device-Manager.app`

3. To create a DMG (optional):
```bash
hdiutil create -volname "AWG-Kumulus-Device-Manager" -srcfolder dist/AWG-Kumulus-Device-Manager.app -ov -format UDZO AWG-Kumulus-Device-Manager.dmg
```

## Testing Builds

After building, test the application:

```bash
# Windows
dist\AWG-Kumulus-Device-Manager.exe

# Linux
dist/AWG-Kumulus-Device-Manager/AWG-Kumulus-Device-Manager

# macOS
open dist/AWG-Kumulus-Device-Manager.app
```

## Troubleshooting

### Import Errors

If you see import errors in the built executable, add the missing modules to the `hiddenimports` list in the spec file.

### File Not Found Errors

Ensure all data files (`machineTypes.json`, etc.) are included in the `datas` section of the spec file.

### Large File Sizes

Consider using UPX compression or excluding unnecessary modules from the build.

