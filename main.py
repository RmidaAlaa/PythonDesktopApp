#!/usr/bin/env python3
"""
AWG Kumulus Device Manager
Cross-platform Python desktop application for managing embedded boards.
"""

import sys
import os
import ctypes
from pathlib import Path
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QGuiApplication, QPixmap, QIcon
from PySide6.QtCore import Qt, qInstallMessageHandler

from src.core.config import Config
from src.core.bootstrap import BootstrapManager
from src.core.version import format_version_banner
from src.core.crash_handler import install_exception_handler
from src.gui.main_window import MainWindow

def qt_message_handler(mode, context, message):
    """Custom Qt message handler to suppress specific internal warnings."""
    # Filter out QWindowsWindow::setGeometry warnings
    if "QWindowsWindow::setGeometry" in message:
        return
    # Write other messages to stderr
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()

def main():
    """Entry point for the application."""
    # Install custom message handler
    qInstallMessageHandler(qt_message_handler)

    # Install crash handler
    install_exception_handler()

    # Ensure application name is set
    QApplication.setApplicationName("AWG Kumulus Device Manager")
    QApplication.setOrganizationName("AWG")
    
    # Set App ID for Windows Taskbar Icon
    if os.name == 'nt':
        myappid = 'awg.kumulus.devicemanager.1.0.0'
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
    
    # High-DPI: use Qt6 rounding policy instead of deprecated attributes
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    # Create Qt application first (needed for Splash Screen)
    app = QApplication(sys.argv)

    # Set Global App Icon
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent

    icon_path = base_path / "src" / "assets" / "logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Show Splash Screen
    splash_pix = QPixmap(str(icon_path))
    # Scale if too big
    if splash_pix.width() > 600:
        splash_pix = splash_pix.scaledToWidth(600, Qt.SmoothTransformation)
    
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.show()
    splash.showMessage("Initializing...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    app.processEvents()

    # Load environment from .env if present (IDE path, workspace overrides, version)
    try:
        root = Path(__file__).resolve().parent
        env_path = root / ".env"
        if not env_path.exists():
            env_path = root.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v:
                        os.environ.setdefault(k, v)
    except Exception:
        pass

    # Initialize config
    Config.ensure_directories()
    
    # Check and download firmware
    try:
        success = BootstrapManager().check_firmware_files()
        if not success:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "Firmware Warning", 
                              "Failed to download required firmware (GetMachineUid.bin).\n"
                              "Some features may not work correctly.\n"
                              "Please check your internet connection.")
    except Exception as e:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "Startup Error", f"Error during firmware check: {str(e)}")
    
    # Create Qt application
    # app = QApplication(sys.argv) # Already created above
    
    # Create and show main window
    window = MainWindow()
    # Log version banner once in the main window logger
    try:
        from src.core.logger import setup_logger
        mw_logger = setup_logger("Startup")
        mw_logger.info(format_version_banner())
    except Exception:
        pass
    
    window.show()
    splash.finish(window) # Close splash screen
    window.raise_()  # Bring window to front
    window.activateWindow()  # Activate the window
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
