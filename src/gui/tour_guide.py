from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
                               QApplication, QDialog)
from PySide6.QtCore import Qt, QPoint, QRect, QSize, QTimer, QCoreApplication
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPolygon, QFont, QPainterPath

class TourBubble(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Remove WindowStaysOnTopHint so it doesn't float over other apps
        # Use Qt.Tool so it stays on top of the parent window (app) but minimizes with it
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Allow focus for keyboard navigation
        self.setFocusPolicy(Qt.StrongFocus)
        
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
        self.next_btn = QPushButton(QCoreApplication.translate("Tour", "Next"))
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
        
        self.skip_btn = QPushButton(QCoreApplication.translate("Tour", "Skip"))
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
        
        self.target_rect = QRect()
        self.arrow_pos = 'left' # left, right, top, bottom relative to bubble
        
    def set_content(self, title, text, step_txt, is_last=False):
        self.title_label.setText(title)
        self.text_label.setText(text)
        self.step_label.setText(step_txt)
        self.next_btn.setText(QCoreApplication.translate("Tour", "Finish") if is_last else QCoreApplication.translate("Tour", "Next"))
        
        # Adjust size hint
        self.adjustSize()
        # Force a repaint to update layout
        self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.skip_btn.hasFocus():
                self.skip_btn.click()
            else:
                self.next_btn.click()
        elif event.key() == Qt.Key_Escape:
            self.skip_btn.click()
        else:
            super().keyPressEvent(event)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Define rect for bubble (keep margins for shadow space)
        rect = self.rect().adjusted(10, 10, -10, -10)
        
        # Create bubble path
        path = QPainterPath()
        path.addRoundedRect(rect, self.border_radius, self.border_radius)
        
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
        
        # Combine paths for seamless shadow and fill
        arrow_path = QPainterPath()
        arrow_path.addPolygon(arrow)
        final_path = path.united(arrow_path)
        
        # Draw Manual Shadow (avoids UpdateLayeredWindowIndirect crash)
        painter.save()
        painter.translate(0, 4)
        painter.setBrush(QColor(0, 0, 0, 60))
        painter.setPen(Qt.NoPen)
        painter.drawPath(final_path)
        painter.restore()
            
        # Draw Main Bubble
        painter.setBrush(self.bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawPath(final_path)

class TourManager:
    def __init__(self, main_window):
        self.window = main_window
        self.bubble = TourBubble(main_window)
        self.bubble.next_btn.clicked.connect(self.next_step)
        self.bubble.skip_btn.clicked.connect(self.end_tour)
        self.is_running = False
        
        self.steps = [
            {
                'target': None,
                'title': QCoreApplication.translate("Tour", "Welcome to AWG Kumulus"),
                'text': QCoreApplication.translate("Tour", "This quick tour will guide you through all features and components of the application."),
                'pos': 'center'
            },
            # --- Device List Section ---
            {
                'target': 'device_table',
                'title': QCoreApplication.translate("Tour", "Device List"),
                'text': QCoreApplication.translate("Tour", "All connected devices appear here. You can see Port, Type, UID, Firmware, and Status."),
                'pos': 'right'
            },
            {
                'target': 'filter_input',
                'title': QCoreApplication.translate("Tour", "Filter Devices"),
                'text': QCoreApplication.translate("Tour", "Type here to filter devices by name, port, or type."),
                'pos': 'bottom'
            },
            {
                'target': 'filter_type_combo',
                'title': QCoreApplication.translate("Tour", "Filter by Type"),
                'text': QCoreApplication.translate("Tour", "Use this dropdown to view only specific board types (e.g., STM32)."),
                'pos': 'bottom'
            },
            # --- Operator Info Section ---
            {
                'target': 'operator_name',
                'title': QCoreApplication.translate("Tour", "Operator Name"),
                'text': QCoreApplication.translate("Tour", "Enter your full name here. This will be included in reports and emails."),
                'pos': 'right'
            },
            {
                'target': 'operator_email',
                'title': QCoreApplication.translate("Tour", "Operator Email"),
                'text': QCoreApplication.translate("Tour", "Provide your email address for support requests and report identification."),
                'pos': 'right'
            },
            {
                'target': 'operator_phone',
                'title': QCoreApplication.translate("Tour", "Phone Number"),
                'text': QCoreApplication.translate("Tour", "Enter your contact number."),
                'pos': 'right'
            },
            {
                'target': 'operator_country',
                'title': QCoreApplication.translate("Tour", "Country (Pays)"),
                'text': QCoreApplication.translate("Tour", "This is auto-detected, but you can correct it if needed."),
                'pos': 'right'
            },
            # --- Machine Info Section ---
            {
                'target': 'client_name',
                'title': QCoreApplication.translate("Tour", "Client Name"),
                'text': QCoreApplication.translate("Tour", "MANDATORY: Enter the client name. Reports and emails cannot be sent without this."),
                'pos': 'right'
            },
            {
                'target': 'machine_type',
                'title': QCoreApplication.translate("Tour", "Machine Type"),
                'text': QCoreApplication.translate("Tour", "Select the type of machine you are working on (e.g., Amphore)."),
                'pos': 'right'
            },
            {
                'target': 'machine_id_suffix',
                'title': QCoreApplication.translate("Tour", "Machine ID"),
                'text': QCoreApplication.translate("Tour", "Select or type the ID suffix. The full ID (Prefix + Suffix) is shown above."),
                'pos': 'right'
            },
            # --- Action Buttons ---
            {
                'target': 'refresh_btn',
                'title': QCoreApplication.translate("Tour", "Refresh Devices"),
                'text': QCoreApplication.translate("Tour", "Click or press Ctrl+R to re-scan for connected devices. UIDs are cleared on refresh."),
                'pos': 'top'
            },
            {
                'target': 'history_btn',
                'title': QCoreApplication.translate("Tour", "Device History"),
                'text': QCoreApplication.translate("Tour", "View a log of all devices detected in this session."),
                'pos': 'top'
            },
            {
                'target': 'email_btn',
                'title': QCoreApplication.translate("Tour", "Send Email"),
                'text': QCoreApplication.translate("Tour", "Send the generated report to configured recipients via SMTP or Azure (Ctrl+E)."),
                'pos': 'top'
            },
            {
                'target': 'flash_btn',
                'title': QCoreApplication.translate("Tour", "Flash Firmware"),
                'text': QCoreApplication.translate("Tour", "Click Next to open the flashing dialog (Ctrl+F)."),
                'pos': 'top'
            },
            {
                'target': 'flash_firmware_dialog',
                'title': QCoreApplication.translate("Tour", "Flash Dialog"),
                'text': QCoreApplication.translate("Tour", "This is the firmware flashing interface. You can interact with it while the tour is active."),
                'pos': 'center',
                'trigger': lambda: self.window.flash_firmware_dialog()
            },
            {
                'target': 'flash_device_list',
                'title': QCoreApplication.translate("Tour", "Select Device"),
                'text': QCoreApplication.translate("Tour", "Select the target device from this list."),
                'pos': 'right'
            },
            {
                'target': 'flash_source_combo',
                'title': QCoreApplication.translate("Tour", "Firmware Source"),
                'text': QCoreApplication.translate("Tour", "Choose where the firmware comes from: Local file, URL, or GitLab."),
                'pos': 'bottom'
            },
            {
                'target': 'flash_file_path',
                'title': QCoreApplication.translate("Tour", "File Path"),
                'text': QCoreApplication.translate("Tour", "Enter the path or URL here, or use the Browse button."),
                'pos': 'bottom'
            },
            {
                'target': 'flash_firmware_dialog',
                'title': QCoreApplication.translate("Tour", "Close Dialog"),
                'text': QCoreApplication.translate("Tour", "Automatically closing the Flash Firmware dialog..."),
                'pos': 'center',
                'trigger': lambda: self.close_target('flash_firmware_dialog')
            },
            {
                'target': 'read_uid_btn',
                'title': QCoreApplication.translate("Tour", "Read UID"),
                'text': QCoreApplication.translate("Tour", "Manually read the Unique ID of a selected device (Ctrl+U)."),
                'pos': 'top'
            },
            {
                'target': 'open_stm32_btn',
                'title': QCoreApplication.translate("Tour", "Open Project"),
                'text': QCoreApplication.translate("Tour", "Click Next to open the project dialog (Ctrl+O)."),
                'pos': 'top'
            },
            {
                'target': 'open_project_dialog',
                'title': QCoreApplication.translate("Tour", "Project Dialog"),
                'text': QCoreApplication.translate("Tour", "This interface allows you to open local projects or clone from Git."),
                'pos': 'center',
                'trigger': lambda: self.window.open_stm32_project_dialog()
            },
            {
                'target': 'open_project_mode_local',
                'title': QCoreApplication.translate("Tour", "Local Mode"),
                'text': QCoreApplication.translate("Tour", "Select 'Use local project path' to open an existing project folder."),
                'pos': 'right'
            },
            {
                'target': 'open_project_mode_git',
                'title': QCoreApplication.translate("Tour", "Git Mode"),
                'text': QCoreApplication.translate("Tour", "Select 'Clone from Git URL' to download a project from a remote repository."),
                'pos': 'right'
            },
            {
                'target': 'open_project_dialog',
                'title': QCoreApplication.translate("Tour", "Close Dialog"),
                'text': QCoreApplication.translate("Tour", "Automatically closing the Open Project dialog..."),
                'pos': 'center',
                'trigger': lambda: self.close_target('open_project_dialog')
            },
            {
                'target': 'settings_btn',
                'title': QCoreApplication.translate("Tour", "Settings"),
                'text': QCoreApplication.translate("Tour", "Click Next to open the Settings menu (Ctrl+S)."),
                'pos': 'top'
            },
            {
                'target': 'settings_menu_dialog',
                'title': QCoreApplication.translate("Tour", "Settings Menu"),
                'text': QCoreApplication.translate("Tour", "Access various configuration options here."),
                'pos': 'center',
                'trigger': lambda: self.window.show_settings_menu()
            },
            {
                'target': 'settings_config_btn',
                'title': QCoreApplication.translate("Tour", "Configuration"),
                'text': QCoreApplication.translate("Tour", "Access protected configuration settings."),
                'pos': 'right'
            },
            {
                'target': 'settings_machine_btn',
                'title': QCoreApplication.translate("Tour", "Machine Types"),
                'text': QCoreApplication.translate("Tour", "Configure machine types and parameters."),
                'pos': 'right'
            },
            {
                'target': 'settings_theme_btn',
                'title': QCoreApplication.translate("Tour", "Themes & Language"),
                'text': QCoreApplication.translate("Tour", "Change the application theme and language."),
                'pos': 'right'
            },
            {
                'target': 'settings_menu_dialog',
                'title': QCoreApplication.translate("Tour", "Close Menu"),
                'text': QCoreApplication.translate("Tour", "Automatically closing the Settings menu..."),
                'pos': 'center',
                'trigger': lambda: self.close_target('settings_menu_dialog')
            },
            # --- Header Icons ---
            {
                'target': 'btn_manual_icon', # Assuming this attribute exists, checking logic below
                'title': QCoreApplication.translate("Tour", "User Manual"),
                'text': QCoreApplication.translate("Tour", "Click here to open the full User Manual (PDF/HTML)."),
                'pos': 'bottom'
            },
            {
                'target': 'btn_support_icon',
                'title': QCoreApplication.translate("Tour", "Contact Support"),
                'text': QCoreApplication.translate("Tour", "Need help? Click here to send logs and a description to support."),
                'pos': 'bottom'
            },
            # --- Status & Footer ---
            {
                'target': 'onedrive_status_label',
                'title': QCoreApplication.translate("Tour", "OneDrive Status"),
                'text': QCoreApplication.translate("Tour", "Shows the current status of OneDrive sync."),
                'pos': 'top'
            },
            {
                'target': 'footer_devices_label',
                'title': QCoreApplication.translate("Tour", "Connected Devices"),
                'text': QCoreApplication.translate("Tour", "Total count of currently connected devices."),
                'pos': 'top'
            },
            {
                'target': 'footer_clock_label',
                'title': QCoreApplication.translate("Tour", "System Time"),
                'text': QCoreApplication.translate("Tour", "Current date and time with UTC offset."),
                'pos': 'top'
            },
            {
                'target': 'footer_geo_label',
                'title': QCoreApplication.translate("Tour", "Location & Timezone"),
                'text': QCoreApplication.translate("Tour", "Detected location and timezone information."),
                'pos': 'top'
            },
            {
                'target': 'btn_tour_icon',
                'title': QCoreApplication.translate("Tour", "Restart Tour"),
                'text': QCoreApplication.translate("Tour", "Click this icon anytime to restart the quick tour."),
                'pos': 'bottom'
            },
            {
                'target': None,
                'title': QCoreApplication.translate("Tour", "Tour Complete"),
                'text': QCoreApplication.translate("Tour", "You are all set! Click Finish to start using the app."),
                'pos': 'center'
            }
        ]
        self.current_step = 0
        
    def start_tour(self):
        self.current_step = 0
        self.is_running = True
        self.show_step()
        
    def next_step(self):
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.end_tour()
            return
            
        step = self.steps[self.current_step]
        trigger = step.get('trigger')
        
        if trigger:
            # Execute trigger (e.g., open dialog) and delay showing step to allow UI to update
            QTimer.singleShot(300, self.show_step)
            trigger()
        else:
            self.show_step()
            
    def end_tour(self):
        self.is_running = False
        self.bubble.hide()

    def close_target(self, target_name):
        """Helper to close a target dialog/widget if found."""
        widget = self.find_target_widget(target_name)
        if widget and isinstance(widget, QDialog):
            widget.accept()
        elif widget:
            widget.close()

    def find_target_widget(self, target_name):
        if not target_name:
            return None
        
        # 1. Try attribute on main window
        widget = getattr(self.window, target_name, None)
        if widget and isinstance(widget, QWidget) and widget.isVisible():
            return widget
            
        # 2. Search all top-level widgets (windows/dialogs)
        # This covers main window, modal dialogs, and other windows
        for top_level in QApplication.topLevelWidgets():
            if not top_level.isVisible() or top_level == self.bubble:
                continue
                
            # Check if top_level itself is the target
            if top_level.objectName() == target_name:
                return top_level
                
            # Search children of this top-level widget
            child = top_level.findChild(QWidget, target_name)
            if child and child.isVisible():
                return child
                
        return None
        
    def on_dialog_finished(self):
        """Handle dialog closing to save bubble and auto-advance."""
        # Reparent bubble to main window immediately to prevent destruction
        if self.bubble.parent() != self.window:
            self.bubble.setParent(self.window)
            self.bubble.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
            self.bubble.show()
            
        # If current step is about closing dialog, advance automatically
        if self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            if "Close" in step['title'] or "close" in step['text'].lower():
                QTimer.singleShot(100, self.next_step)
            else:
                # Just refresh position (will center on main window if target lost)
                QTimer.singleShot(100, self.show_step)

    def show_step(self):
        step = self.steps[self.current_step]
        
        target_widget = self.find_target_widget(step['target'])
            
        # If target widget is not visible or not found, try to skip or fallback
        if step['target'] and (not target_widget or not target_widget.isVisible()):
            # Just show in center if target missing
            target_widget = None

        # Dynamic reparenting for modal dialogs
        if target_widget:
            target_window = target_widget.window()
            
            # Hook into dialog finished event if it's a dialog
            if isinstance(target_window, QDialog):
                try:
                    target_window.finished.connect(self.on_dialog_finished, Qt.UniqueConnection)
                except Exception:
                    pass
            
            # If target is in a different window than current bubble parent
            if target_window != self.bubble.parent():
                self.bubble.setParent(target_window)
                # Re-apply flags because setParent clears them sometimes
                self.bubble.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
                self.bubble.show()
        else:
             # Fallback to main window if lost
             if self.bubble.parent() != self.window:
                 self.bubble.setParent(self.window)
                 self.bubble.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
                 self.bubble.show()
            
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
        
        # Explicitly set focus to the Next button so Enter key works immediately
        QTimer.singleShot(100, self.bubble.next_btn.setFocus)
        
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
        
        # Determine screen geometry
        screen = QApplication.screenAt(global_pos)
        if not screen:
            screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()

        # Define position calculations
        def get_rect(pos_name):
            rect = QRect(0, 0, bubble_size.width(), bubble_size.height())
            if pos_name == 'right':
                rect.moveLeft(target_rect.right() + spacing)
                rect.moveTop(target_rect.center().y() - bubble_size.height() // 2)
            elif pos_name == 'left':
                rect.moveRight(target_rect.left() - spacing)
                rect.moveTop(target_rect.center().y() - bubble_size.height() // 2)
            elif pos_name == 'top':
                rect.moveBottom(target_rect.top() - spacing)
                rect.moveLeft(target_rect.center().x() - bubble_size.width() // 2)
            elif pos_name == 'bottom':
                rect.moveTop(target_rect.bottom() + spacing)
                rect.moveLeft(target_rect.center().x() - bubble_size.width() // 2)
            return rect

        # Preference order: preferred -> opposite -> others
        order = [pref_pos]
        opposites = {'right': 'left', 'left': 'right', 'top': 'bottom', 'bottom': 'top'}
        if pref_pos in opposites:
            order.append(opposites[pref_pos])
        
        # Add remaining directions
        for p in ['right', 'left', 'bottom', 'top']:
            if p not in order:
                order.append(p)

        best_pos = pref_pos
        best_rect = get_rect(pref_pos)
        
        found_fit = False
        for pos_name in order:
            rect = get_rect(pos_name)
            # Check if fully contained in screen
            if screen_geo.contains(rect):
                best_pos = pos_name
                best_rect = rect
                found_fit = True
                break
        
        # If no perfect fit, use the one with most overlap or just clamp the preferred/best found
        # For now, we stick with the best_rect found (or the last one tried if logic fails, but here we init with pref)
        
        # Final clamp to screen to ensure visibility (e.g. if bubble is larger than screen or close to edge)
        if best_rect.left() < screen_geo.left(): best_rect.moveLeft(screen_geo.left())
        if best_rect.right() > screen_geo.right(): best_rect.moveRight(screen_geo.right())
        if best_rect.top() < screen_geo.top(): best_rect.moveTop(screen_geo.top())
        if best_rect.bottom() > screen_geo.bottom(): best_rect.moveBottom(screen_geo.bottom())

        self.bubble.move(best_rect.topLeft())
        
        # Set arrow position (opposite of bubble position relative to target)
        arrow_map = {'right': 'left', 'left': 'right', 'top': 'bottom', 'bottom': 'top'}
        self.bubble.arrow_pos = arrow_map.get(best_pos, 'left')
        self.bubble.update() # Trigger repaint

class DialogTourManager(TourManager):
    def __init__(self, dialog, steps):
        self.window = dialog
        self.bubble = TourBubble(dialog)
        self.bubble.next_btn.clicked.connect(self.next_step)
        self.bubble.skip_btn.clicked.connect(self.end_tour)
        self.is_running = False
        self.steps = steps
        self.current_step = 0
