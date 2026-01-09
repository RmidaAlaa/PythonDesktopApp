"""
Translation utilities using QCoreApplication.translate().
Provides proper Qt translation support with pylupdate compatibility.

Implements full i18n logic:
- Language enum with locale codes (en_US, fr_FR)
- QTranslator management and dynamic switching
- QLocale default setting for number/date formatting
- .qm loading from translations/ directory (app data and project root)
"""

from PySide6.QtCore import QCoreApplication, QTranslator, QLocale, QSettings, Qt
from PySide6.QtWidgets import QApplication
import os
from pathlib import Path

from .config import Config
from .logger import setup_logger

logger = setup_logger("TranslationManager")


class Language:
    """Language constants with locale codes."""
    ENGLISH = "en"      # en_US
    FRENCH = "fr"       # fr_FR

    @staticmethod
    def to_locale_code(lang: str) -> str:
        return {
            Language.ENGLISH: "en_US",
            Language.FRENCH: "fr_FR",
        }.get(lang, "en_US")

    @staticmethod
    def is_rtl(lang: str) -> bool:
        # No RTL languages supported in current configuration
        return False


class TranslationManager:
    """Manages Qt translations using QCoreApplication.translate()."""
    
    def __init__(self):
        self.translator = QTranslator()
        self.current_language = Language.ENGLISH
        self.translations_dir = Path(Config.get_app_data_dir()) / "translations"
        self.translations_dir.mkdir(exist_ok=True)
        
        # Load saved language
        self._load_saved_language()
        self._apply_locale_and_direction()
        self._load_translation()
    
    def _load_saved_language(self):
        """Load saved language from settings or legacy config."""
        try:
            # Prefer QSettings per i18n requirements
            settings = QSettings("AWG", "KumulusDeviceManager")
            saved = settings.value("language", None)
            if isinstance(saved, str) and saved in (Language.ENGLISH, Language.FRENCH):
                self.current_language = saved
                return

            # Legacy fallback: language.json
            config_file = Path(Config.get_app_data_dir()) / "language.json"
            if config_file.exists():
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    legacy_lang = data.get('language', Language.ENGLISH)
                    if legacy_lang in (Language.ENGLISH, Language.FRENCH):
                        self.current_language = legacy_lang
                        # Migrate to QSettings
                        settings.setValue("language", legacy_lang)
                        return
                    else:
                        # Previously saved unknown code -> fallback to English
                        self.current_language = Language.ENGLISH
                        settings.setValue("language", self.current_language)
                        return
        except Exception as e:
            logger.error(f"Failed to load saved language: {e}")
            self.current_language = Language.ENGLISH
    
    def _save_language(self):
        """Persist current language to QSettings (and legacy file for compatibility)."""
        try:
            settings = QSettings("AWG", "KumulusDeviceManager")
            settings.setValue("language", self.current_language)
            # Also write legacy file to keep older versions in sync
            config_file = Path(Config.get_app_data_dir()) / "language.json"
            import json
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump({'language': self.current_language}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save language: {e}")

    def _apply_locale_and_direction(self):
        """Set default locale and layout direction based on current language."""
        app = QApplication.instance()
        # Set default QLocale for number/date formatting
        locale_code = Language.to_locale_code(self.current_language)
        try:
            locale = QLocale(locale_code)
            QLocale.setDefault(locale)
            logger.debug(f"Set QLocale default to {locale_code}")
        except Exception as e:
            logger.debug(f"Failed to set QLocale {locale_code}: {e}")
        # Set application layout direction
        if app:
            app.setLayoutDirection(Qt.RightToLeft if Language.is_rtl(self.current_language) else Qt.LeftToRight)
    
    def _load_translation(self) -> bool:
        """Load translation file for current language.
        
        Returns True if a translation was loaded, False otherwise.
        """
        app = QApplication.instance()
        if not app:
            return False

        # Remove any existing translator first
        app.removeTranslator(self.translator)

        # English uses no translator
        if self.current_language == Language.ENGLISH:
            return True

        loaded = False

        # Primary: user app-data translations
        translation_file = self.translations_dir / f"app_{self.current_language}.qm"
        if translation_file.exists():
            if self.translator.load(str(translation_file)):
                app.installTranslator(self.translator)
                logger.info(f"Loaded translation from app data: {self.current_language}")
                loaded = True
            else:
                logger.warning(f"Failed to load app-data translation: {self.current_language}")

        # Fallback: project translations directory (developer environment)
        if not loaded:
            try:
                from pathlib import Path as _Path
                project_dir = _Path(__file__).resolve().parents[2]  # repo root
                fallback = project_dir / "translations" / f"app_{self.current_language}.qm"
                if fallback.exists() and self.translator.load(str(fallback)):
                    app.installTranslator(self.translator)
                    logger.info(f"Loaded translation from project: {self.current_language}")
                    loaded = True
            except Exception as e:
                logger.debug(f"Fallback translation load error: {e}")

        if not loaded:
            # Ensure we run with English and without a translator
            app.removeTranslator(self.translator)
            logger.warning(f"No translation file found for: {self.current_language}. Falling back to English.")

        return loaded
    
    def set_language(self, language_code: str):
        """Set application language.
        Applies the translator if available; otherwise falls back to English.
        """
        self.current_language = language_code
        # Apply locale and layout first to ensure immediate UI direction change
        self._apply_locale_and_direction()
        loaded = self._load_translation()
        if loaded:
            self._save_language()
            logger.info(f"Language changed to: {language_code}")
        else:
        # Fall back to English and persist the fallback to avoid repeated warnings
            self.current_language = Language.ENGLISH
            self._save_language()
            logger.info("Translation missing; language set to English (fallback)")
    
    def get_current_language(self) -> str:
        """Get current language code."""
        return self.current_language

    def get_language_code(self) -> str:
        return self.get_current_language()
    
    def is_rtl_language(self) -> bool:
        """Check if current language is right-to-left."""
        return Language.is_rtl(self.current_language)


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
    from PySide6.QtCore import QCoreApplication
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
    FRENCH = lambda: tr(TrContext.SETTINGS, "French")
