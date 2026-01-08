
from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
                               QGraphicsDropShadowEffect, QApplication)
from PySide6.QtCore import Qt, QPoint, QRect, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPolygon, QFont, QPainterPath

class TourBubble(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Style configuration
        self.bg_color = QColor("#6200ee")  # Purple
        self.text_color = QColor("#ffffff")
        self.border_radius = 8
        self.arrow_size = 10
        self.padding = 15
        
        # Content
        self.title_label = QLabel()
        self.title_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: white; font-size: 12px;")
        
        self.step_label = QLabel()
        self.step_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 10px;")
        
        # Buttons
        self.next_btn = QPushButton("Next")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #6200ee;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.8);
                border: none;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        
        # Layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 20, 20, 20)  # Room for shadow/arrow
        
        # Container for content to apply margins safely
        content_layout = QVBoxLayout()
        content_layout.setSpacing(8)
        
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.text_label)
        
        # Footer
        footer_layout = QHBoxLayout()
        footer_layout.addWidget(self.step_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.skip_btn)
        footer_layout.addWidget(self.next_btn)
        
        content_layout.addLayout(footer_layout)
        self.main_layout.addLayout(content_layout)
        self.setLayout(self.main_layout)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        self.target_rect = QRect()
        self.arrow_pos = 'left' # left, right, top, bottom relative to bubble
        
    def set_content(self, title, text, step_txt, is_last=False):
        self.title_label.setText(title)
        self.text_label.setText(text)
        self.step_label.setText(step_txt)
        self.next_btn.setText("Finish" if is_last else "Next")
        
        # Adjust size hint
        self.adjustSize()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw bubble
        path = QPainterPath()
        rect = self.rect().adjusted(10, 10, -10, -10) # Adjust for shadow margin
        
        path.addRoundedRect(rect, self.border_radius, self.border_radius)
        
        painter.fillPath(path, self.bg_color)
        
        # Arrow logic
        arrow = QPolygon()
        center_x = rect.center().x()
        center_y = rect.center().y()
        
        if self.arrow_pos == 'left': # Arrow on left side of bubble (pointing left)
            tip = QPoint(rect.left() - self.arrow_size, center_y)
            base1 = QPoint(rect.left(), center_y - self.arrow_size)
            base2 = QPoint(rect.left(), center_y + self.arrow_size)
            arrow << tip << base1 << base2
        elif self.arrow_pos == 'right':
            tip = QPoint(rect.right() + self.arrow_size, center_y)
            base1 = QPoint(rect.right(), center_y - self.arrow_size)
            base2 = QPoint(rect.right(), center_y + self.arrow_size)
            arrow << tip << base1 << base2
        elif self.arrow_pos == 'top':
            tip = QPoint(center_x, rect.top() - self.arrow_size)
            base1 = QPoint(center_x - self.arrow_size, rect.top())
            base2 = QPoint(center_x + self.arrow_size, rect.top())
            arrow << tip << base1 << base2
        elif self.arrow_pos == 'bottom':
            tip = QPoint(center_x, rect.bottom() + self.arrow_size)
            base1 = QPoint(center_x - self.arrow_size, rect.bottom())
            base2 = QPoint(center_x + self.arrow_size, rect.bottom())
            arrow << tip << base1 << base2
            
        painter.setBrush(self.bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(arrow)

class TourManager:
    def __init__(self, main_window):
        self.window = main_window
        self.bubble = TourBubble()
        self.bubble.next_btn.clicked.connect(self.next_step)
        self.bubble.skip_btn.clicked.connect(self.end_tour)
        
        self.steps = [
            {
                'target': None,
                'title': 'Welcome to AWG Kumulus',
                'text': 'This quick tour will guide you through all features and components of the application.',
                'pos': 'center'
            },
            # --- Device List Section ---
            {
                'target': 'device_table',
                'title': 'Device List',
                'text': 'All connected devices appear here. You can see Port, Type, UID, Firmware, and Status.',
                'pos': 'right'
            },
            {
                'target': 'filter_input',
                'title': 'Filter Devices',
                'text': 'Type here to filter devices by name, port, or type.',
                'pos': 'bottom'
            },
            {
                'target': 'filter_type_combo',
                'title': 'Filter by Type',
                'text': 'Use this dropdown to view only specific board types (e.g., STM32).',
                'pos': 'bottom'
            },
            # --- Operator Info Section ---
            {
                'target': 'operator_name',
                'title': 'Operator Name',
                'text': 'Enter your full name here. This will be included in reports and emails.',
                'pos': 'right'
            },
            {
                'target': 'operator_email',
                'title': 'Operator Email',
                'text': 'Provide your email address for support requests and report identification.',
                'pos': 'right'
            },
            {
                'target': 'operator_phone',
                'title': 'Phone Number',
                'text': 'Enter your contact number.',
                'pos': 'right'
            },
            {
                'target': 'operator_country',
                'title': 'Country (Pays)',
                'text': 'This is auto-detected, but you can correct it if needed.',
                'pos': 'right'
            },
            # --- Machine Info Section ---
            {
                'target': 'client_name',
                'title': 'Client Name',
                'text': 'MANDATORY: Enter the client name. Reports and emails cannot be sent without this.',
                'pos': 'right'
            },
            {
                'target': 'machine_type',
                'title': 'Machine Type',
                'text': 'Select the type of machine you are working on (e.g., Amphore).',
                'pos': 'right'
            },
            {
                'target': 'machine_id_suffix',
                'title': 'Machine ID',
                'text': 'Select or type the ID suffix. The full ID (Prefix + Suffix) is shown above.',
                'pos': 'right'
            },
            # --- Action Buttons ---
            {
                'target': 'refresh_btn',
                'title': 'Refresh Devices',
                'text': 'Click to re-scan for connected devices. UIDs are cleared on refresh.',
                'pos': 'top'
            },
            {
                'target': 'history_btn',
                'title': 'Device History',
                'text': 'View a log of all devices detected in this session.',
                'pos': 'top'
            },
            {
                'target': 'email_btn',
                'title': 'Send Email',
                'text': 'Send the generated report to configured recipients via SMTP or Azure.',
                'pos': 'top'
            },
            {
                'target': 'flash_btn',
                'title': 'Flash Firmware',
                'text': 'Open the flashing dialog to update device firmware or restore backups.',
                'pos': 'top'
            },
            {
                'target': 'read_uid_btn',
                'title': 'Read UID',
                'text': 'Manually read the Unique ID of a selected device.',
                'pos': 'top'
            },
            {
                'target': 'open_stm32_btn',
                'title': 'Open Project',
                'text': 'Quickly open the STM32 project folder or VS Code workspace.',
                'pos': 'top'
            },
            {
                'target': 'settings_btn',
                'title': 'Settings',
                'text': 'Configure Email, OneDrive, App Defaults, and Initialize App Data.',
                'pos': 'top'
            },
            # --- Header Icons ---
            {
                'target': 'btn_manual_icon', # Assuming this attribute exists, checking logic below
                'title': 'User Manual',
                'text': 'Click here to open the full User Manual (PDF/HTML).',
                'pos': 'bottom'
            },
            {
                'target': 'btn_support_icon',
                'title': 'Contact Support',
                'text': 'Need help? Click here to send logs and a description to support.',
                'pos': 'bottom'
            },
            # --- Status & Footer ---
            {
                'target': 'onedrive_status_label',
                'title': 'OneDrive Status',
                'text': 'Shows the current status of OneDrive sync.',
                'pos': 'top'
            },
            {
                'target': 'footer_devices_label',
                'title': 'Connected Devices',
                'text': 'Total count of currently connected devices.',
                'pos': 'top'
            },
            {
                'target': 'footer_clock_label',
                'title': 'System Time',
                'text': 'Current date and time with UTC offset.',
                'pos': 'top'
            },
            {
                'target': 'footer_geo_label',
                'title': 'Location & Timezone',
                'text': 'Detected location and timezone information.',
                'pos': 'top'
            },
            {
                'target': 'btn_tour_icon',
                'title': 'Restart Tour',
                'text': 'Click this icon anytime to restart the quick tour.',
                'pos': 'bottom'
            },
            {
                'target': None,
                'title': 'Tour Complete',
                'text': 'You are all set! Click Finish to start using the app.',
                'pos': 'center'
            }
        ]
        self.current_step = 0
        
    def start_tour(self):
        self.current_step = 0
        self.show_step()
        
    def next_step(self):
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.end_tour()
        else:
            self.show_step()
            
    def end_tour(self):
        self.bubble.hide()
        
    def show_step(self):
        step = self.steps[self.current_step]
        
        target_widget = None
        if step['target']:
            target_widget = getattr(self.window, step['target'], None)
            
        # If target widget is not visible or not found, try to skip or fallback
        if step['target'] and (not target_widget or not target_widget.isVisible()):
            # Just show in center if target missing
            target_widget = None
            
        self.bubble.set_content(
            step['title'], 
            step['text'], 
            f"{self.current_step + 1} of {len(self.steps)}",
            is_last=(self.current_step == len(self.steps) - 1)
        )
        
        # Position bubble
        self.position_bubble(target_widget, step.get('pos', 'right'))
        self.bubble.show()
        self.bubble.raise_()
        
    def position_bubble(self, target, pref_pos):
        if not target:
            # Center on main window
            win_geo = self.window.geometry()
            bubble_geo = self.bubble.sizeHint()
            x = win_geo.x() + (win_geo.width() - bubble_geo.width()) // 2
            y = win_geo.y() + (win_geo.height() - bubble_geo.height()) // 2
            self.bubble.move(x, y)
            self.bubble.arrow_pos = None # No arrow
            return

        # Get global rect of target
        global_pos = target.mapToGlobal(QPoint(0, 0))
        target_rect = QRect(global_pos, target.size())
        
        bubble_size = self.bubble.sizeHint()
        # Ensure bubble size is calculated
        self.bubble.resize(bubble_size)
        
        spacing = 15 # Gap between arrow tip and target
        
        x, y = 0, 0
        
        # Calculate positions
        # Right
        if pref_pos == 'right':
            x = target_rect.right() + spacing
            y = target_rect.center().y() - bubble_size.height() // 2
            self.bubble.arrow_pos = 'left'
            
            # Check if offscreen
            screen_geo = QApplication.primaryScreen().geometry()
            if x + bubble_size.width() > screen_geo.right():
                pref_pos = 'left' # Flip to left
        
        # Left
        if pref_pos == 'left':
            x = target_rect.left() - bubble_size.width() - spacing
            y = target_rect.center().y() - bubble_size.height() // 2
            self.bubble.arrow_pos = 'right'
            
        # Top
        if pref_pos == 'top':
            x = target_rect.center().x() - bubble_size.width() // 2
            y = target_rect.top() - bubble_size.height() - spacing
            self.bubble.arrow_pos = 'bottom'
            
        # Bottom
        if pref_pos == 'bottom':
            x = target_rect.center().x() - bubble_size.width() // 2
            y = target_rect.bottom() + spacing
            self.bubble.arrow_pos = 'top'
            
        self.bubble.move(x, y)
