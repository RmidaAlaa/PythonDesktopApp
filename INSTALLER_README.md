# Installer Build Instructions

This guide explains how to build the "Next -> Next" professional installer for the AWG Kumulus Device Manager using Inno Setup.

## 1. Prerequisites

1.  **Install Inno Setup**: Download and install the latest version (Unicode) from [jrsoftware.org](https://jrsoftware.org/isdl.php).
2.  **Build the Application**:
    Ensure you have built the latest EXE:
    ```bash
    pyinstaller build_windows.spec
    ```
    Verify `dist/AWG-Kumulus-Device-Manager.exe` exists.

## 2. Prepare Dependency Installers

The installer requires external installers for the dependencies. You must download them and place them in a `prerequisites` folder.

1.  Create a folder named `prerequisites` in the `PythonDesktopApp` directory.
2.  **Visual C++ Redistributable (x64)**:
    *   Download `vc_redist.x64.exe` from Microsoft.
    *   Save it as `prerequisites\vc_redist.x64.exe`.
3.  **ST-Link Drivers**:
    *   Download the driver installer (e.g., `dpinst_amd64.exe` or signed setup exe) from ST.com.
    *   Save it as `prerequisites\stlink_driver.exe`.
4.  **CP210x Drivers**:
    *   Download the CP210x VCP Installer from Silicon Labs.
    *   Save it as `prerequisites\cp210x_driver.exe`.

> **Note**: If you don't have the driver installers handy, you can comment out the `Source: ... Check: IsSTLinkNeeded` lines in `setup.iss` to skip them for testing.

## 3. Build the Installer

1.  Open `setup.iss` in Inno Setup Compiler.
2.  Press **F9** or click **Build -> Compile**.
3.  The final installer `AWG-Kumulus-Installer.exe` will be created in the `Output` folder (or project root).

## 4. Installer Logic

*   **Detection**: It automatically checks the Registry for VC++ Redistributable and `System32\drivers` for specific driver files (`stlink_winusb.sys`, `silabser.sys`).
*   **UI**: It shows a "Required Components" page listing status (Installed/Missing).
*   **Auto-Install**: Clicking "Next" silently installs any missing components before proceeding to the main app installation.
