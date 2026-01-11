"""
Theme Manager for the Desktop Application.
Handles different visual themes (Dark, Light, Custom).
"""

from PySide6.QtCore import QObject, Signal, QCoreApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication
from enum import Enum
from typing import Dict, Any
import json
from pathlib import Path

from .config import Config
from .logger import setup_logger

logger = setup_logger("ThemeManager")


class ThemeType(Enum):
    """Available theme types."""
    LIGHT = "light"
    DARK = "dark"
    CUSTOM = "custom"


class ThemeManager(QObject):
    """Manages application themes and styling."""
    
    theme_changed = Signal(str)  # Emitted when theme changes
    
    def __init__(self):
        super().__init__()
        self.current_theme = ThemeType.LIGHT
        self.themes_file = Path(Config.get_app_data_dir()) / "themes.json"
        self.custom_themes: Dict[str, Dict[str, Any]] = {}
        
        # Load saved themes
        self._load_themes()
        
        # Apply default theme
        self.apply_theme(self.current_theme)
    
    def _load_themes(self):
        """Load custom themes from file."""
        try:
            if self.themes_file.exists():
                with open(self.themes_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.custom_themes = data.get('custom_themes', {})
                    current_theme_name = data.get('current_theme', 'light')
                    
                    # Set current theme
                    if current_theme_name in [t.value for t in ThemeType]:
                        self.current_theme = ThemeType(current_theme_name)
                    else:
                        self.current_theme = ThemeType.LIGHT
                        
        except Exception as e:
            logger.error(f"Failed to load themes: {e}")
            self.current_theme = ThemeType.LIGHT
    
    def _save_themes(self):
        """Save themes to file."""
        try:
            data = {
                'current_theme': self.current_theme.value,
                'custom_themes': self.custom_themes
            }
            
            with open(self.themes_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save themes: {e}")
    
    def get_available_themes(self) -> Dict[str, str]:
        """Get list of available themes."""
        themes = {
            QCoreApplication.translate("ThemeManager", "☀️ Light Mode"): ThemeType.LIGHT.value,
            QCoreApplication.translate("ThemeManager", "🌙 Dark Mode"): ThemeType.DARK.value,
        }
        
        # Add custom themes
        for name, theme_data in self.custom_themes.items():
            themes[f"🎨 {name}"] = f"custom_{name}"
        
        return themes
    
    def apply_theme(self, theme_type: ThemeType):
        """Apply a theme to the application."""
        app = QApplication.instance()
        if not app:
            return
        
        palette = QPalette()
        
        if theme_type == ThemeType.LIGHT:
            self._apply_light_theme(palette)
        elif theme_type == ThemeType.DARK:
            self._apply_dark_theme(palette)
        elif theme_type == ThemeType.CUSTOM:
            # Apply the first custom theme if available
            if self.custom_themes:
                first_custom = list(self.custom_themes.keys())[0]
                self._apply_custom_theme(palette, self.custom_themes[first_custom])
            else:
                self._apply_light_theme(palette)
        
        app.setPalette(palette)
        try:
            app.setStyleSheet(self.get_theme_stylesheet(theme_type))
        except Exception:
            pass
        self.current_theme = theme_type
        self._save_themes()
        self.theme_changed.emit(theme_type.value)
        
        logger.info(f"Applied theme: {theme_type.value}")
    
    def apply_theme_by_name(self, theme_name: str):
        """Apply theme by name."""
        if theme_name == ThemeType.LIGHT.value:
            self.apply_theme(ThemeType.LIGHT)
        elif theme_name == ThemeType.DARK.value:
            self.apply_theme(ThemeType.DARK)
        elif theme_name.startswith("custom_"):
            custom_name = theme_name[7:]  # Remove "custom_" prefix
            if custom_name in self.custom_themes:
                self._apply_custom_theme_by_name(custom_name)
    
    def _apply_custom_theme_by_name(self, custom_name: str):
        """Apply custom theme by name."""
        if custom_name not in self.custom_themes:
            return
        
        app = QApplication.instance()
        if not app:
            return
        
        palette = QPalette()
        self._apply_custom_theme(palette, self.custom_themes[custom_name])
        
        app.setPalette(palette)
        self.current_theme = ThemeType.CUSTOM
        self._save_themes()
        self.theme_changed.emit(f"custom_{custom_name}")
        
        logger.info(f"Applied custom theme: {custom_name}")
    
    def _apply_light_theme(self, palette: QPalette):
        """Apply light theme colors."""
        # Base colors - Clean and modern light theme
        palette.setColor(QPalette.Window, QColor(248, 249, 250))  # Very light gray
        palette.setColor(QPalette.WindowText, QColor(33, 37, 41))  # Dark gray text
        palette.setColor(QPalette.Base, QColor(255, 255, 255))  # Pure white
        palette.setColor(QPalette.AlternateBase, QColor(240, 242, 245))  # Light gray
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))  # Light yellow
        palette.setColor(QPalette.ToolTipText, QColor(33, 37, 41))  # Dark text
        palette.setColor(QPalette.Text, QColor(33, 37, 41))  # Dark text
        palette.setColor(QPalette.Button, QColor(233, 236, 239))  # Light button
        palette.setColor(QPalette.ButtonText, QColor(33, 37, 41))  # Dark button text
        palette.setColor(QPalette.BrightText, QColor(220, 53, 69))  # Red for errors
        palette.setColor(QPalette.Link, QColor(0, 123, 255))  # Blue links
        palette.setColor(QPalette.Highlight, QColor(0, 123, 255))  # Blue highlight
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))  # White on highlight
    
    def _apply_dark_theme(self, palette: QPalette):
        """Apply dark theme colors."""
        # Base colors - Modern dark theme
        palette.setColor(QPalette.Window, QColor(33, 37, 41))  # Dark gray background
        palette.setColor(QPalette.WindowText, QColor(248, 249, 250))  # Light text
        palette.setColor(QPalette.Base, QColor(52, 58, 64))  # Darker base
        palette.setColor(QPalette.AlternateBase, QColor(73, 80, 87))  # Medium dark
        palette.setColor(QPalette.ToolTipBase, QColor(52, 58, 64))  # Dark tooltip
        palette.setColor(QPalette.ToolTipText, QColor(248, 249, 250))  # Light tooltip text
        palette.setColor(QPalette.Text, QColor(248, 249, 250))  # Light text
        palette.setColor(QPalette.Button, QColor(73, 80, 87))  # Dark button
        palette.setColor(QPalette.ButtonText, QColor(248, 249, 250))  # Light button text
        palette.setColor(QPalette.BrightText, QColor(255, 107, 107))  # Light red for errors
        palette.setColor(QPalette.Link, QColor(64, 224, 255))  # Light blue links
        palette.setColor(QPalette.Highlight, QColor(64, 224, 255))  # Light blue highlight
        palette.setColor(QPalette.HighlightedText, QColor(33, 37, 41))  # Dark text on highlight
    
    def _apply_custom_theme(self, palette: QPalette, theme_data: Dict[str, Any]):
        """Apply custom theme colors."""
        colors = theme_data.get('colors', {})
        
        # Apply custom colors or fallback to light theme
        palette.setColor(QPalette.Window, QColor(colors.get('window', '#FFFFFF')))
        palette.setColor(QPalette.WindowText, QColor(colors.get('window_text', '#000000')))
        palette.setColor(QPalette.Base, QColor(colors.get('base', '#FFFFFF')))
        palette.setColor(QPalette.AlternateBase, QColor(colors.get('alternate_base', '#F0F0F0')))
        palette.setColor(QPalette.ToolTipBase, QColor(colors.get('tooltip_base', '#FFFFDC')))
        palette.setColor(QPalette.ToolTipText, QColor(colors.get('tooltip_text', '#000000')))
        palette.setColor(QPalette.Text, QColor(colors.get('text', '#000000')))
        palette.setColor(QPalette.Button, QColor(colors.get('button', '#F0F0F0')))
        palette.setColor(QPalette.ButtonText, QColor(colors.get('button_text', '#000000')))
        palette.setColor(QPalette.BrightText, QColor(colors.get('bright_text', '#FF0000')))
        palette.setColor(QPalette.Link, QColor(colors.get('link', '#2A82DA')))
        palette.setColor(QPalette.Highlight, QColor(colors.get('highlight', '#2A82DA')))
        palette.setColor(QPalette.HighlightedText, QColor(colors.get('highlighted_text', '#FFFFFF')))
    
    def create_custom_theme(self, name: str, colors: Dict[str, str], description: str = ""):
        """Create a new custom theme."""
        self.custom_themes[name] = {
            'colors': colors,
            'description': description,
            'created_at': str(Path().cwd())  # Simple timestamp placeholder
        }
        self._save_themes()
        logger.info(f"Created custom theme: {name}")
    
    def delete_custom_theme(self, name: str):
        """Delete a custom theme."""
        if name in self.custom_themes:
            del self.custom_themes[name]
            self._save_themes()
            logger.info(f"Deleted custom theme: {name}")
    
    def get_current_theme(self) -> str:
        """Get current theme name."""
        return self.current_theme.value
    
    def get_theme_stylesheet(self, theme_type: ThemeType) -> str:
        """Get additional stylesheet for theme."""
        if theme_type == ThemeType.DARK:
            return """
            /* Dark Theme Stylesheet */
            QMainWindow {
                background-color: #212529;
                color: #f8f9fa;
            }
            QTabWidget::pane {
                border: 1px solid #495057;
                background-color: #343a40;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #495057;
                color: #f8f9fa;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #40e0ff;
                color: #212529;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #6c757d;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #495057;
                border-radius: 6px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #343a40;
                color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #40e0ff;
            }
            QPushButton {
                background-color: #495057;
                color: #f8f9fa;
                border: 1px solid #6c757d;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6c757d;
                border-color: #40e0ff;
            }
            QPushButton:pressed {
                background-color: #343a40;
            }
            QTableWidget {
                background-color: #343a40;
                alternate-background-color: #495057;
                color: #f8f9fa;
                border: 1px solid #495057;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #495057;
            }
            QTableWidget::item:selected {
                background-color: #40e0ff;
                color: #212529;
            }
            QHeaderView::section {
                background-color: #495057;
                color: #f8f9fa;
                padding: 8px;
                border: 1px solid #6c757d;
                font-weight: bold;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #343a40;
                color: #f8f9fa;
                border: 1px solid #495057;
                border-radius: 4px;
                padding: 4px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #40e0ff;
            }
            QProgressBar {
                border: 1px solid #495057;
                border-radius: 4px;
                background-color: #343a40;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #40e0ff;
                border-radius: 3px;
            }
            QScrollBar:vertical {
                background-color: #343a40;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #495057;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #6c757d;
            }
            """
        elif theme_type == ThemeType.LIGHT:
            return """
            /* Light Theme Stylesheet */
            QMainWindow {
                background-color: #f8f9fa;
                color: #212529;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                background-color: #ffffff;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                color: #212529;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #007bff;
                color: #ffffff;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #ffffff;
                color: #212529;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #007bff;
            }
            QPushButton {
                background-color: #e9ecef;
                color: #212529;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #007bff;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
                color: #212529;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
            }
            QTableWidget::item:selected {
                background-color: #007bff;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                color: #212529;
                padding: 8px;
                border: 1px solid #ced4da;
                font-weight: bold;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #ffffff;
                color: #212529;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #007bff;
            }
            QProgressBar {
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #ffffff;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007bff;
                border-radius: 3px;
            }
            QScrollBar:vertical {
                background-color: #ffffff;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #e9ecef;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #ced4da;
            }
            """
        else:
            return ""
