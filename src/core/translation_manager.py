"""
Translation utilities using QCoreApplication.translate().
Provides proper Qt translation support with pylupdate compatibility.
"""

from PySide6.QtCore import QCoreApplication, QTranslator, QLocale
from PySide6.QtWidgets import QApplication
import os
from pathlib import Path

from .config import Config
from .logger import setup_logger

logger = setup_logger("TranslationManager")


class TranslationManager:
    """Manages Qt translations using QCoreApplication.translate()."""
    
    def __init__(self):
        self.translator = QTranslator()
        self.current_language = "en"
        self.translations_dir = Path(Config.get_app_data_dir()) / "translations"
        self.translations_dir.mkdir(exist_ok=True)
        
        # Load saved language
        self._load_saved_language()
        self._load_translation()
    
    def _load_saved_language(self):
        """Load saved language from config."""
        try:
            config_file = Path(Config.get_app_data_dir()) / "language.json"
            if config_file.exists():
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.current_language = data.get('language', 'en')
        except Exception as e:
            logger.error(f"Failed to load saved language: {e}")
            self.current_language = "en"
    
    def _save_language(self):
        """Save current language to config."""
        try:
            config_file = Path(Config.get_app_data_dir()) / "language.json"
            import json
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump({'language': self.current_language}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save language: {e}")
    
    def _load_translation(self):
        """Load translation file for current language."""
        app = QApplication.instance()
        if not app:
            return
        
        # Remove existing translator
        app.removeTranslator(self.translator)
        
        # Load new translation if not English
        if self.current_language != "en":
            translation_file = self.translations_dir / f"app_{self.current_language}.qm"
            if translation_file.exists():
                if self.translator.load(str(translation_file)):
                    app.installTranslator(self.translator)
                    logger.info(f"Loaded translation: {self.current_language}")
                else:
                    logger.warning(f"Failed to load translation: {self.current_language}")
    
    def set_language(self, language_code: str):
        """Set application language."""
        self.current_language = language_code
        self._save_language()
        self._load_translation()
        logger.info(f"Language changed to: {language_code}")
    
    def get_current_language(self) -> str:
        """Get current language code."""
        return self.current_language
    
    def is_rtl_language(self) -> bool:
        """Check if current language is right-to-left."""
        return self.current_language == "ar"


def tr(context: str, text: str, disambiguation: str = None, n: int = -1) -> str:
    """
    Translation function compatible with pylupdate.
    
    Args:
        context: Translation context (usually class name)
        text: Text to translate
        disambiguation: Disambiguation text for ambiguous translations
        n: Number for plural forms
    
    Returns:
        Translated text
    """
    return QCoreApplication.translate(context, text, disambiguation, n)


# Common translation contexts
class TrContext:
    """Translation contexts for different parts of the application."""
    
    # Main window
    MAIN_WINDOW = "MainWindow"
    
    # Device management
    DEVICE_MANAGER = "DeviceManager"
    
    # Settings
    SETTINGS = "Settings"
    
    # Dialogs
    DIALOGS = "Dialogs"
    
    # Messages
    MESSAGES = "Messages"


# Predefined translated strings for common UI elements
class TrStrings:
    """Common translated strings."""
    
    # Main interface
    APP_TITLE = lambda: tr(TrContext.MAIN_WINDOW, "AWG Kumulus Device Manager v1.0.0")
    REFRESH_DEVICES = lambda: tr(TrContext.MAIN_WINDOW, "Refresh Devices")
    DEVICE_HISTORY = lambda: tr(TrContext.MAIN_WINDOW, "Device History")
    DEVICE_TEMPLATES = lambda: tr(TrContext.MAIN_WINDOW, "Device Templates")
    SEARCH_DEVICES = lambda: tr(TrContext.MAIN_WINDOW, "Search Devices")
    
    # Actions
    FLASH_FIRMWARE = lambda: tr(TrContext.MAIN_WINDOW, "Flash Firmware")
    GENERATE_REPORT = lambda: tr(TrContext.MAIN_WINDOW, "Generate Report")
    SEND_EMAIL = lambda: tr(TrContext.MAIN_WINDOW, "Send Email")
    ONEDRIVE_SYNC = lambda: tr(TrContext.MAIN_WINDOW, "OneDrive Sync")
    
    # Settings
    EMAIL_SETTINGS = lambda: tr(TrContext.SETTINGS, "Email Settings")
    MACHINE_SETTINGS = lambda: tr(TrContext.SETTINGS, "Machine Settings")
    ONEDRIVE_SETTINGS = lambda: tr(TrContext.SETTINGS, "OneDrive Settings")
    THEME_LANGUAGE = lambda: tr(TrContext.SETTINGS, "Theme & Language")
    
    # Device information
    DEVICE_NAME = lambda: tr(TrContext.DEVICE_MANAGER, "Device Name")
    DEVICE_TYPE = lambda: tr(TrContext.DEVICE_MANAGER, "Device Type")
    PORT = lambda: tr(TrContext.DEVICE_MANAGER, "Port")
    STATUS = lambda: tr(TrContext.DEVICE_MANAGER, "Status")
    HEALTH_SCORE = lambda: tr(TrContext.DEVICE_MANAGER, "Health Score")
    LAST_SEEN = lambda: tr(TrContext.DEVICE_MANAGER, "Last Seen")
    
    # Status messages
    CONNECTED = lambda: tr(TrContext.MESSAGES, "Connected")
    DISCONNECTED = lambda: tr(TrContext.MESSAGES, "Disconnected")
    UNKNOWN = lambda: tr(TrContext.MESSAGES, "Unknown")
    LOADING = lambda: tr(TrContext.MESSAGES, "Loading")
    
    # Common actions
    OK = lambda: tr(TrContext.DIALOGS, "OK")
    CANCEL = lambda: tr(TrContext.DIALOGS, "Cancel")
    APPLY = lambda: tr(TrContext.DIALOGS, "Apply")
    SAVE = lambda: tr(TrContext.DIALOGS, "Save")
    DELETE = lambda: tr(TrContext.DIALOGS, "Delete")
    CREATE = lambda: tr(TrContext.DIALOGS, "Create")
    EDIT = lambda: tr(TrContext.DIALOGS, "Edit")
    CLOSE = lambda: tr(TrContext.DIALOGS, "Close")
    REFRESH = lambda: tr(TrContext.DIALOGS, "Refresh")
    SEARCH = lambda: tr(TrContext.DIALOGS, "Search")
    BROWSE = lambda: tr(TrContext.DIALOGS, "Browse")
    
    # Themes
    LIGHT_THEME = lambda: tr(TrContext.SETTINGS, "Light Mode")
    DARK_THEME = lambda: tr(TrContext.SETTINGS, "Dark Mode")
    CUSTOM_THEME = lambda: tr(TrContext.SETTINGS, "Custom Theme")
    
    # Languages
    ENGLISH = lambda: tr(TrContext.SETTINGS, "English")
    ARABIC = lambda: tr(TrContext.SETTINGS, "Arabic")
    FRENCH = lambda: tr(TrContext.SETTINGS, "French")
