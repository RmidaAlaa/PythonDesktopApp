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


def _adjust_color(hex_color: str, delta: int) -> str:
    """Lighten or darken a hex color by delta (-255..255)."""
    h = hex_color.lstrip('#')
    if len(h) != 6:
        return hex_color
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    r = max(0, min(255, r + delta))
    g = max(0, min(255, g + delta))
    b = max(0, min(255, b + delta))
    return f"#{r:02x}{g:02x}{b:02x}"


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
    base = c['highlight']
    light = _adjust_color(base, 40)
    dark = _adjust_color(base, -25)
    hover_light = _adjust_color(base, 60)
    hover_dark = _adjust_color(base, 0)
    press_light = _adjust_color(base, -10)
    press_dark = _adjust_color(base, -50)
    return f"""
    QPushButton, QToolButton {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 {light}, stop:1 {dark});
        color: {c['highlight_text']};
        border: 1px solid {dark};
        padding: 12px 24px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 14px;
    }}
    QPushButton:hover, QToolButton:hover {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 {hover_light}, stop:1 {hover_dark});
        border: 2px solid {hover_light};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 {press_light}, stop:1 {press_dark});
        border: 2px solid {press_dark};
        color: {c['highlight_text']};
        padding-top: 14px; /* subtle press effect */
        padding-bottom: 10px;
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