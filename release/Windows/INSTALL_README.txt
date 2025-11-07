AWG Kumulus Device Manager — Windows Installation Guide

Requirements:
- Windows 10/11 (64-bit)
- Standard user account is sufficient
- Internet access recommended on first run (to auto-download helper tools)

Install / Run:
1) Copy `AWG-Kumulus-Device-Manager.exe` to the laptop (e.g., Desktop).
2) Double-click to launch.
   - If Windows SmartScreen shows a warning:
     • Click “More info” → “Run anyway”.

Notes:
- Serial/USB access: Ensure technicians have permission to access COM ports.
- First run: The app may download helper binaries (e.g., esptool/avrdude).
- Updates: Replace the old `.exe` with the new one to update.
- Logs: The app writes logs in the user’s app-data folder.

Localization:
- The app defaults to English if translation files are not installed.
- For French support, install Qt Linguist tools and rebuild `.qm` files.

Support:
- If you see missing module warnings, contact support to get a new build.
- To report issues, provide the machine type, ID, and steps to reproduce.