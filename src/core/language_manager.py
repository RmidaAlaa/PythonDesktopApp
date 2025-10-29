"""
Language Manager for the Desktop Application.
Handles multi-language support (Arabic, French, English).
"""

from PySide6.QtCore import QObject, Signal
from enum import Enum
from typing import Dict, Any
import json
from pathlib import Path

from .config import Config
from .logger import setup_logger

logger = setup_logger("LanguageManager")


class LanguageType(Enum):
    """Available language types."""
    ENGLISH = "en"
    ARABIC = "ar"
    FRENCH = "fr"


class LanguageManager(QObject):
    """Manages application languages and translations."""
    
    language_changed = Signal(str)  # Emitted when language changes
    
    def __init__(self):
        super().__init__()
        self.current_language = LanguageType.ENGLISH
        self.translations = {}
        self.languages_file = Path(Config.get_app_data_dir()) / "languages.json"
        
        # Load translations
        self._load_translations()
        
        # Load saved language
        self._load_saved_language()
    
    def _load_translations(self):
        """Load all translations."""
        self.translations = {
            LanguageType.ENGLISH.value: {
                # Main Interface
                "app_title": "AWG Kumulus Device Manager v1.0.0",
                "device_manager": "Device Manager",
                "firmware_manager": "Firmware Manager",
                "settings": "Settings",
                "help": "Help",
                
                # Device Management
                "refresh_devices": "Refresh Devices",
                "device_history": "Device History",
                "device_templates": "Device Templates",
                "search_devices": "Search Devices",
                "flash_firmware": "Flash Firmware",
                "generate_report": "Generate Report",
                "send_email": "Send Email",
                "onedrive_sync": "OneDrive Sync",
                
                # Device Information
                "device_name": "Device Name",
                "device_type": "Device Type",
                "port": "Port",
                "status": "Status",
                "firmware_version": "Firmware Version",
                "health_score": "Health Score",
                "last_seen": "Last Seen",
                "connection_count": "Connection Count",
                
                # Status Messages
                "connected": "Connected",
                "disconnected": "Disconnected",
                "unknown": "Unknown",
                "detected": "Detected",
                "new_device": "New Device",
                "device_disconnected": "Device Disconnected",
                
                # Settings
                "theme_settings": "Theme Settings",
                "language_settings": "Language Settings",
                "email_settings": "Email Settings",
                "machine_settings": "Machine Settings",
                "onedrive_settings": "OneDrive Settings",
                
                # Themes
                "light_theme": "Light Theme",
                "dark_theme": "Dark Theme",
                "custom_theme": "Custom Theme",
                "apply_theme": "Apply Theme",
                "create_custom_theme": "Create Custom Theme",
                "theme_name": "Theme Name",
                "window_color": "Window Color",
                "text_color": "Text Color",
                "button_color": "Button Color",
                "highlight_color": "Highlight Color",
                "choose_color": "Choose Color",
                
                # Languages
                "english": "English",
                "arabic": "Arabic",
                "french": "French",
                "select_language": "Select Language",
                "apply_language": "Apply Language",
                
                # Common Actions
                "ok": "OK",
                "cancel": "Cancel",
                "apply": "Apply",
                "save": "Save",
                "delete": "Delete",
                "create": "Create",
                "edit": "Edit",
                "close": "Close",
                "refresh": "Refresh",
                "search": "Search",
                "browse": "Browse",
                "upload": "Upload",
                "download": "Download",
                
                # Messages
                "theme_applied": "Theme Applied",
                "language_applied": "Language Applied",
                "settings_saved": "Settings Saved",
                "operation_successful": "Operation Successful",
                "operation_failed": "Operation Failed",
                "please_wait": "Please Wait",
                "loading": "Loading",
                "error": "Error",
                "warning": "Warning",
                "information": "Information",
                "success": "Success",
                
                # Device Types
                "esp32": "ESP32",
                "esp8266": "ESP8266",
                "stm32": "STM32",
                "arduino": "Arduino",
                "unknown_device": "Unknown Device",
            },
            
            LanguageType.ARABIC.value: {
                # Main Interface
                "app_title": "مدير أجهزة AWG Kumulus الإصدار 1.0.0",
                "device_manager": "مدير الأجهزة",
                "firmware_manager": "مدير البرامج الثابتة",
                "settings": "الإعدادات",
                "help": "المساعدة",
                
                # Device Management
                "refresh_devices": "تحديث الأجهزة",
                "device_history": "تاريخ الأجهزة",
                "device_templates": "قوالب الأجهزة",
                "search_devices": "البحث في الأجهزة",
                "flash_firmware": "تثبيت البرنامج الثابت",
                "generate_report": "إنشاء تقرير",
                "send_email": "إرسال بريد إلكتروني",
                "onedrive_sync": "مزامنة OneDrive",
                
                # Device Information
                "device_name": "اسم الجهاز",
                "device_type": "نوع الجهاز",
                "port": "المنفذ",
                "status": "الحالة",
                "firmware_version": "إصدار البرنامج الثابت",
                "health_score": "درجة الصحة",
                "last_seen": "آخر ظهور",
                "connection_count": "عدد الاتصالات",
                
                # Status Messages
                "connected": "متصل",
                "disconnected": "غير متصل",
                "unknown": "غير معروف",
                "detected": "تم اكتشافه",
                "new_device": "جهاز جديد",
                "device_disconnected": "تم قطع الاتصال بالجهاز",
                
                # Settings
                "theme_settings": "إعدادات المظهر",
                "language_settings": "إعدادات اللغة",
                "email_settings": "إعدادات البريد الإلكتروني",
                "machine_settings": "إعدادات الجهاز",
                "onedrive_settings": "إعدادات OneDrive",
                
                # Themes
                "light_theme": "المظهر الفاتح",
                "dark_theme": "المظهر الداكن",
                "custom_theme": "مظهر مخصص",
                "apply_theme": "تطبيق المظهر",
                "create_custom_theme": "إنشاء مظهر مخصص",
                "theme_name": "اسم المظهر",
                "window_color": "لون النافذة",
                "text_color": "لون النص",
                "button_color": "لون الزر",
                "highlight_color": "لون التمييز",
                "choose_color": "اختيار اللون",
                
                # Languages
                "english": "الإنجليزية",
                "arabic": "العربية",
                "french": "الفرنسية",
                "select_language": "اختيار اللغة",
                "apply_language": "تطبيق اللغة",
                
                # Common Actions
                "ok": "موافق",
                "cancel": "إلغاء",
                "apply": "تطبيق",
                "save": "حفظ",
                "delete": "حذف",
                "create": "إنشاء",
                "edit": "تعديل",
                "close": "إغلاق",
                "refresh": "تحديث",
                "search": "بحث",
                "browse": "تصفح",
                "upload": "رفع",
                "download": "تحميل",
                
                # Messages
                "theme_applied": "تم تطبيق المظهر",
                "language_applied": "تم تطبيق اللغة",
                "settings_saved": "تم حفظ الإعدادات",
                "operation_successful": "تمت العملية بنجاح",
                "operation_failed": "فشلت العملية",
                "please_wait": "يرجى الانتظار",
                "loading": "جاري التحميل",
                "error": "خطأ",
                "warning": "تحذير",
                "information": "معلومات",
                "success": "نجح",
                
                # Device Types
                "esp32": "ESP32",
                "esp8266": "ESP8266",
                "stm32": "STM32",
                "arduino": "Arduino",
                "unknown_device": "جهاز غير معروف",
            },
            
            LanguageType.FRENCH.value: {
                # Main Interface
                "app_title": "Gestionnaire d'Appareils AWG Kumulus v1.0.0",
                "device_manager": "Gestionnaire d'Appareils",
                "firmware_manager": "Gestionnaire de Firmware",
                "settings": "Paramètres",
                "help": "Aide",
                
                # Device Management
                "refresh_devices": "Actualiser les Appareils",
                "device_history": "Historique des Appareils",
                "device_templates": "Modèles d'Appareils",
                "search_devices": "Rechercher des Appareils",
                "flash_firmware": "Flasher le Firmware",
                "generate_report": "Générer un Rapport",
                "send_email": "Envoyer un Email",
                "onedrive_sync": "Synchronisation OneDrive",
                
                # Device Information
                "device_name": "Nom de l'Appareil",
                "device_type": "Type d'Appareil",
                "port": "Port",
                "status": "Statut",
                "firmware_version": "Version du Firmware",
                "health_score": "Score de Santé",
                "last_seen": "Dernière Vue",
                "connection_count": "Nombre de Connexions",
                
                # Status Messages
                "connected": "Connecté",
                "disconnected": "Déconnecté",
                "unknown": "Inconnu",
                "detected": "Détecté",
                "new_device": "Nouvel Appareil",
                "device_disconnected": "Appareil Déconnecté",
                
                # Settings
                "theme_settings": "Paramètres de Thème",
                "language_settings": "Paramètres de Langue",
                "email_settings": "Paramètres Email",
                "machine_settings": "Paramètres Machine",
                "onedrive_settings": "Paramètres OneDrive",
                
                # Themes
                "light_theme": "Thème Clair",
                "dark_theme": "Thème Sombre",
                "custom_theme": "Thème Personnalisé",
                "apply_theme": "Appliquer le Thème",
                "create_custom_theme": "Créer un Thème Personnalisé",
                "theme_name": "Nom du Thème",
                "window_color": "Couleur de Fenêtre",
                "text_color": "Couleur de Texte",
                "button_color": "Couleur de Bouton",
                "highlight_color": "Couleur de Surbrillance",
                "choose_color": "Choisir la Couleur",
                
                # Languages
                "english": "Anglais",
                "arabic": "Arabe",
                "french": "Français",
                "select_language": "Sélectionner la Langue",
                "apply_language": "Appliquer la Langue",
                
                # Common Actions
                "ok": "OK",
                "cancel": "Annuler",
                "apply": "Appliquer",
                "save": "Sauvegarder",
                "delete": "Supprimer",
                "create": "Créer",
                "edit": "Modifier",
                "close": "Fermer",
                "refresh": "Actualiser",
                "search": "Rechercher",
                "browse": "Parcourir",
                "upload": "Télécharger",
                "download": "Télécharger",
                
                # Messages
                "theme_applied": "Thème Appliqué",
                "language_applied": "Langue Appliquée",
                "settings_saved": "Paramètres Sauvegardés",
                "operation_successful": "Opération Réussie",
                "operation_failed": "Opération Échouée",
                "please_wait": "Veuillez Patienter",
                "loading": "Chargement",
                "error": "Erreur",
                "warning": "Avertissement",
                "information": "Information",
                "success": "Succès",
                
                # Device Types
                "esp32": "ESP32",
                "esp8266": "ESP8266",
                "stm32": "STM32",
                "arduino": "Arduino",
                "unknown_device": "Appareil Inconnu",
            }
        }
    
    def _load_saved_language(self):
        """Load saved language from file."""
        try:
            if self.languages_file.exists():
                with open(self.languages_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    current_lang = data.get('current_language', 'en')
                    
                    if current_lang in [l.value for l in LanguageType]:
                        self.current_language = LanguageType(current_lang)
                    else:
                        self.current_language = LanguageType.ENGLISH
                        
        except Exception as e:
            logger.error(f"Failed to load language: {e}")
            self.current_language = LanguageType.ENGLISH
    
    def _save_language(self):
        """Save current language to file."""
        try:
            data = {
                'current_language': self.current_language.value
            }
            
            with open(self.languages_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save language: {e}")
    
    def get_available_languages(self) -> Dict[str, str]:
        """Get list of available languages."""
        return {
            "English": LanguageType.ENGLISH.value,
            "Arabic": LanguageType.ARABIC.value,
            "French": LanguageType.FRENCH.value,
        }
    
    def apply_language(self, language_type: LanguageType):
        """Apply a language to the application."""
        self.current_language = language_type
        self._save_language()
        self.language_changed.emit(language_type.value)
        logger.info(f"Applied language: {language_type.value}")
    
    def apply_language_by_name(self, language_name: str):
        """Apply language by name."""
        if language_name == LanguageType.ENGLISH.value:
            self.apply_language(LanguageType.ENGLISH)
        elif language_name == LanguageType.ARABIC.value:
            self.apply_language(LanguageType.ARABIC)
        elif language_name == LanguageType.FRENCH.value:
            self.apply_language(LanguageType.FRENCH)
    
    def get_text(self, key: str) -> str:
        """Get translated text for a key."""
        return self.translations.get(self.current_language.value, {}).get(key, key)
    
    def get_current_language(self) -> str:
        """Get current language name."""
        return self.current_language.value
    
    def is_rtl_language(self) -> bool:
        """Check if current language is right-to-left."""
        return self.current_language == LanguageType.ARABIC
