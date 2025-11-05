"""
Shared UI style helpers that adapt to the active theme palette.
Centralize common styles to reduce duplication and hardcoded colors.
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette


def _palette_colors():
    app = QApplication.instance()
    palette = app.palette() if app else QPalette()
    return {
        "window": palette.color(QPalette.Window).name(),
        "text": palette.color(QPalette.WindowText).name(),
        "base": palette.color(QPalette.Base).name(),
        "alt_base": palette.color(QPalette.AlternateBase).name(),
        "button": palette.color(QPalette.Button).name(),
        "button_text": palette.color(QPalette.ButtonText).name(),
        "highlight": palette.color(QPalette.Highlight).name(),
        "highlight_text": palette.color(QPalette.HighlightedText).name(),
    }


def card_frame_style(selected: bool) -> str:
    """Return a QFrame stylesheet driven by the current palette."""
    c = _palette_colors()
    border = c["highlight"] if selected else c["alt_base"]
    bg = c["base"] if not selected else c["alt_base"]
    hover_border = c["highlight"]
    hover_bg = c["alt_base"]
    if selected:
        return f"""
        QFrame {{
            border: 2px solid {border};
            border-radius: 8px;
            background-color: {bg};
        }}
        """
    else:
        return f"""
        QFrame {{
            border: 1px solid {border};
            border-radius: 8px;
            background-color: {bg};
        }}
        QFrame:hover {{
            border: 2px solid {hover_border};
            background-color: {hover_bg};
        }}
        """


def primary_button_style() -> str:
    """Palette-aware primary button style."""
    c = _palette_colors()
    return f"""
    QPushButton {{
        background-color: {c['highlight']};
        color: {c['highlight_text']};
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        opacity: 0.9;
    }}
    """


def secondary_button_style() -> str:
    """Palette-aware secondary button style using button colors."""
    c = _palette_colors()
    return f"""
    QPushButton {{
        background-color: {c['button']};
        color: {c['button_text']};
        border: 1px solid {c['alt_base']};
        padding: 10px 20px;
        border-radius: 5px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        border-color: {c['highlight']};
    }}
    """