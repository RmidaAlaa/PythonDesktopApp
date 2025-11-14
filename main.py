#!/usr/bin/env python3
"""
AWG Kumulus Device Manager
Cross-platform Python desktop application for managing embedded boards.
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt

from src.core.config import Config
from src.core.bootstrap import BootstrapManager
from src.core.version import format_version_banner
from src.gui.main_window import MainWindow


def main():
    """Entry point for the application."""
    # Ensure application name is set
    QApplication.setApplicationName("AWG Kumulus Device Manager")
    QApplication.setOrganizationName("AWG")
    
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
    
    # High-DPI: use Qt6 rounding policy instead of deprecated attributes
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    # Create Qt application
    app = QApplication(sys.argv)
    
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
    window.raise_()  # Bring window to front
    window.activateWindow()  # Activate the window
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
