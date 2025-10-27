#!/usr/bin/env python3
"""
AWG Kumulus Device Manager
Cross-platform Python desktop application for managing embedded boards.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

from src.core.config import Config
from src.gui.main_window import MainWindow


def main():
    """Entry point for the application."""
    # Ensure application name is set
    QApplication.setApplicationName("AWG Kumulus Device Manager")
    QApplication.setOrganizationName("AWG")
    
    # Initialize config
    Config.ensure_directories()
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    window.raise_()  # Bring window to front
    window.activateWindow()  # Activate the window
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

