import sys
import traceback
import logging
from PySide6.QtWidgets import QMessageBox, QApplication
from .logger import setup_logger

def install_exception_handler():
    """Install global exception handler."""
    sys.excepthook = handle_exception

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler."""
    # Ignore KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Log the error
    try:
        logger = setup_logger("CrashHandler")
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    except Exception:
        # Fallback if logger fails
        print("Critical error:", exc_value)
        traceback.print_tb(exc_traceback)
    
    # Show error dialog if GUI is running
    if QApplication.instance():
        try:
            error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            
            box = QMessageBox()
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("Critical Error")
            box.setText(f"An unexpected error occurred:\n{str(exc_value)}")
            box.setDetailedText(error_msg)
            box.setStandardButtons(QMessageBox.Ok)
            box.exec()
        except Exception:
            pass
