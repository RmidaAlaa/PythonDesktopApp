"""
Visual Theme Selection Dialog.
Provides a card-based interface for theme selection.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QFrame, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPalette

from ..core.theme_manager import ThemeManager, ThemeType
from ..core.language_manager import LanguageManager, LanguageType


class ThemeCard(QFrame):
    """A card widget representing a theme."""
    
    theme_selected = Signal(str)  # Emitted when theme is selected
    
    def __init__(self, theme_name: str, theme_type: ThemeType, is_selected: bool = False):
        super().__init__()
        self.theme_name = theme_name
        self.theme_type = theme_type
        self.is_selected = is_selected
        
        self.setFixedSize(200, 150)
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(2)
        
        self.setup_ui()
        self.update_selection()
    
    def setup_ui(self):
        """Set up the card UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Theme preview
        self.preview_widget = QWidget()
        self.preview_widget.setFixedSize(180, 100)
        self.preview_widget.setStyleSheet(self.get_preview_style())
        
        # Theme name label
        self.name_label = QLabel(self.theme_name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("Arial", 10, QFont.Bold))
        
        # Selection indicator
        self.selection_label = QLabel("✓")
        self.selection_label.setAlignment(Qt.AlignCenter)
        self.selection_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.selection_label.setStyleSheet("color: #007bff;")
        
        layout.addWidget(self.preview_widget)
        layout.addWidget(self.name_label)
        layout.addWidget(self.selection_label)
        
        self.setLayout(layout)
    
    def get_preview_style(self) -> str:
        """Get preview style based on theme type."""
        if self.theme_type == ThemeType.LIGHT:
            return """
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff, stop:0.5 #f8f9fa, stop:1 #e9ecef);
                border: 2px solid #dee2e6;
                border-radius: 8px;
            }
            """
        elif self.theme_type == ThemeType.DARK:
            return """
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #212529, stop:0.5 #343a40, stop:1 #495057);
                border: 2px solid #6c757d;
                border-radius: 8px;
            }
            """
        else:  # Custom theme
            return """
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6f42c1, stop:0.5 #5a32a3, stop:1 #4c2a85);
                border: 2px solid #5a32a3;
                border-radius: 8px;
            }
            """
    
    def update_selection(self):
        """Update selection appearance."""
        if self.is_selected:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #007bff;
                    border-radius: 8px;
                    background-color: #e3f2fd;
                }
            """)
            self.selection_label.setVisible(True)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    background-color: #ffffff;
                }
                QFrame:hover {
                    border: 2px solid #6c757d;
                    background-color: #f8f9fa;
                }
            """)
            self.selection_label.setVisible(False)
    
    def set_selected(self, selected: bool):
        """Set selection state."""
        self.is_selected = selected
        self.update_selection()
    
    def mousePressEvent(self, event):
        """Handle mouse press to select theme."""
        if event.button() == Qt.LeftButton:
            self.theme_selected.emit(self.theme_type.value)
        super().mousePressEvent(event)


class LanguageCard(QFrame):
    """A card widget representing a language."""
    
    language_selected = Signal(str)  # Emitted when language is selected
    
    def __init__(self, language_name: str, language_type: LanguageType, is_selected: bool = False):
        super().__init__()
        self.language_name = language_name
        self.language_type = language_type
        self.is_selected = is_selected
        
        self.setFixedSize(150, 100)
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(2)
        
        self.setup_ui()
        self.update_selection()
    
    def setup_ui(self):
        """Set up the card UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Language flag/icon (simplified)
        self.flag_label = QLabel(self.get_flag_emoji())
        self.flag_label.setAlignment(Qt.AlignCenter)
        self.flag_label.setFont(QFont("Arial", 24))
        
        # Language name
        self.name_label = QLabel(self.language_name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("Arial", 10, QFont.Bold))
        
        # Selection indicator
        self.selection_label = QLabel("✓")
        self.selection_label.setAlignment(Qt.AlignCenter)
        self.selection_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.selection_label.setStyleSheet("color: #007bff;")
        
        layout.addWidget(self.flag_label)
        layout.addWidget(self.name_label)
        layout.addWidget(self.selection_label)
        
        self.setLayout(layout)
    
    def get_flag_emoji(self) -> str:
        """Get flag emoji for language."""
        if self.language_type == LanguageType.ENGLISH:
            return "🇺🇸"
        elif self.language_type == LanguageType.ARABIC:
            return "🇸🇦"
        elif self.language_type == LanguageType.FRENCH:
            return "🇫🇷"
        return "🌐"
    
    def update_selection(self):
        """Update selection appearance."""
        if self.is_selected:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #007bff;
                    border-radius: 8px;
                    background-color: #e3f2fd;
                }
            """)
            self.selection_label.setVisible(True)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    background-color: #ffffff;
                }
                QFrame:hover {
                    border: 2px solid #6c757d;
                    background-color: #f8f9fa;
                }
            """)
            self.selection_label.setVisible(False)
    
    def set_selected(self, selected: bool):
        """Set selection state."""
        self.is_selected = selected
        self.update_selection()
    
    def mousePressEvent(self, event):
        """Handle mouse press to select language."""
        if event.button() == Qt.LeftButton:
            self.language_selected.emit(self.language_type.value)
        super().mousePressEvent(event)


class ThemeLanguageSelectionDialog(QDialog):
    """Dialog for selecting theme and language."""
    
    def __init__(self, theme_manager: ThemeManager, translation_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.translation_manager = translation_manager
        
        self.theme_cards = {}
        self.language_cards = {}
        
        self.setWindowTitle("Theme & Language Selection")
        self.setMinimumSize(800, 600)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Choose Your Theme & Language")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #007bff; margin: 10px;")
        layout.addWidget(title_label)
        
        # Theme Selection
        theme_section = QLabel("Select Theme:")
        theme_section.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(theme_section)
        
        # Theme cards container
        theme_scroll = QScrollArea()
        theme_scroll.setWidgetResizable(True)
        theme_scroll.setMaximumHeight(200)
        
        theme_widget = QWidget()
        theme_layout = QHBoxLayout()
        
        # Create theme cards
        themes = self.theme_manager.get_available_themes()
        for display_name, theme_value in themes.items():
            if theme_value == "light":
                theme_type = ThemeType.LIGHT
            elif theme_value == "dark":
                theme_type = ThemeType.DARK
            else:
                theme_type = ThemeType.CUSTOM
            
            is_selected = theme_value == self.theme_manager.get_current_theme()
            
            card = ThemeCard(display_name, theme_type, is_selected)
            card.theme_selected.connect(self.on_theme_selected)
            
            self.theme_cards[theme_value] = card
            theme_layout.addWidget(card)
        
        theme_widget.setLayout(theme_layout)
        theme_scroll.setWidget(theme_widget)
        layout.addWidget(theme_scroll)
        
        # Language Selection
        language_section = QLabel("Select Language:")
        language_section.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(language_section)
        
        # Language cards container
        language_scroll = QScrollArea()
        language_scroll.setWidgetResizable(True)
        language_scroll.setMaximumHeight(150)
        
        language_widget = QWidget()
        language_layout = QHBoxLayout()
        
        # Create language cards
        languages = {
            "🇺🇸 English": "en",
            "🇸🇦 العربية": "ar", 
            "🇫🇷 Français": "fr"
        }
        
        for display_name, language_value in languages.items():
            if language_value == "en":
                language_type = LanguageType.ENGLISH
            elif language_value == "ar":
                language_type = LanguageType.ARABIC
            elif language_value == "fr":
                language_type = LanguageType.FRENCH
            
            is_selected = language_value == self.translation_manager.get_current_language()
            
            card = LanguageCard(display_name, language_type, is_selected)
            card.language_selected.connect(self.on_language_selected)
            
            self.language_cards[language_value] = card
            language_layout.addWidget(card)
        
        language_widget.setLayout(language_layout)
        language_scroll.setWidget(language_widget)
        layout.addWidget(language_scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        apply_btn = QPushButton("Apply Selection")
        apply_btn.clicked.connect(self.apply_selection)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(apply_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_theme_selected(self, theme_value: str):
        """Handle theme selection."""
        # Update all theme cards
        for card_value, card in self.theme_cards.items():
            card.set_selected(card_value == theme_value)
    
    def on_language_selected(self, language_value: str):
        """Handle language selection."""
        # Update all language cards
        for card_value, card in self.language_cards.items():
            card.set_selected(card_value == language_value)
    
    def apply_selection(self):
        """Apply selected theme and language."""
        # Apply theme
        for theme_value, card in self.theme_cards.items():
            if card.is_selected:
                self.theme_manager.apply_theme_by_name(theme_value)
                break
        
        # Apply language
        for language_value, card in self.language_cards.items():
            if card.is_selected:
                self.translation_manager.set_language(language_value)
                break
        
        self.accept()
