from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint

class ToastOverlay(QWidget):
    """A non-blocking toast notification overlay."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Setup UI
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 10, 20, 10)
        
        self.label = QLabel()
        self.label.setStyleSheet("""
            QLabel {
                background-color: #333333;
                color: white;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)
        
        # Opacity effect for fading
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # Animation
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_toast)
        
        self.hide()

    def show_message(self, message, duration=2000):
        """Show the toast with a message."""
        self.label.setText(message)
        self.label.adjustSize()
        self.adjustSize()
        
        # Center horizontally, position near bottom
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            y = parent_rect.height() - self.height() - 50
            self.move(x, y)
        
        self.show()
        self.opacity_effect.setOpacity(0)
        
        # Fade in
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()
        
        # Start timer to hide
        self.timer.start(duration)

    def hide_toast(self):
        """Fade out and hide."""
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(self.close)
        self.anim.start()
