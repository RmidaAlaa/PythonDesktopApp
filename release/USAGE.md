# AWG-Kumulus Desktop — Usage Guide

This guide explains how to use the app and its key functionalities.

## Getting Started
- Run the app using `run_app.bat` on Windows.
- On first run, the app creates an app data directory for settings and logs.
- Configure your operator name and email in the Control panel.

## Device Detection
- The app automatically scans for connected devices.
- Use the Devices panel to view ports, board types, VID:PID, status, and health.
- The status bar shows `Devices found: N` on the left.

## Language & Localization
- The language selector is available in the status bar (right side).
- Supported languages: English (`en`), French (`fr`).
- Date and time in the footer are localized using your system locale.
- The footer shows local time with UTC offset, timezone, and approximate location.

## Reports and Email
- Click `[REPORT] Generate Excel Report` to create a device report.
- Configure SMTP under Settings → `Configure Email`.
- Click `[EMAIL] Send Email` to email the latest report to your recipients.

## Firmware Flashing
- Use `[FLASH] Flash Firmware` to flash supported devices (STM32, ESP32/8266, AVR).
- Follow on-screen prompts for boot modes and verification.

## OneDrive Integration
- Configure OneDrive in Settings → `OneDrive` to sync reports.
- The app can auto-create user folder structures and test connectivity.

## Contact Support
- Use Settings → `[SUPPORT] Contact Support` to report issues.
- Provide a short description of the problem; optionally include logs.
- The app will send your description and logs to `armida@kumuluswater.com`.

## Footer Layout
- Left: `Devices found: N`.
- Middle: Localized date/time, UTC offset, timezone, location.
- Right: Language selector.

## Privacy
- Location is detected via network request (best effort) and is approximate.
- No personal data is stored; logs contain app events and technical details.

## Logs
- Logs are saved under the app data directory (e.g., `%APPDATA%/AWG-Kumulus/logs`).
- The support dialog can bundle these logs into a zip for emailing.

## Troubleshooting
- If email fails, ensure SMTP settings are correct and credentials are saved.
- If devices are not detected, try re-scanning or reconnecting the device.

## Version
- This guide applies to app version `1.0.0` and later.