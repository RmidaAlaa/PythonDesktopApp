"""Main application window."""

import sys
import os
import time
import serial
import platform
import socket
from pathlib import Path
import locale
import zipfile
import re
import requests
from typing import Dict, Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QProgressBar, QMessageBox,
    QGroupBox, QSplitter, QApplication, QHeaderView, QDialog,
    QDialogButtonBox, QCheckBox, QFileDialog, QListWidget, QListWidgetItem,
    QSpinBox, QTabWidget, QInputDialog, QMenu, QFormLayout, QStyledItemDelegate,
    QProgressDialog, QScrollArea, QFrame, QStackedWidget
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRegularExpression, QCoreApplication, QLocale, QDateTime, QUrl, QProcess, QSize, QPoint
from PySide6.QtGui import QFont, QRegularExpressionValidator, QDesktopServices, QIcon, QKeySequence, QColor, QPainter, QShortcut, QGuiApplication, QAction, QCursor
from PySide6.QtWidgets import QStyle, QSizePolicy

from ..core.config import Config
from ..core.device_detector import DeviceDetector, Device, BoardType
from ..core.report_generator import ReportGenerator
from ..core.email_sender import EmailSender
from ..core.firmware_flasher import FirmwareFlasher
from ..core.bootstrap import BootstrapManager
from ..core.logger import setup_logger
from ..core.theme_manager import ThemeManager, ThemeType
from ..core.translation_manager import TranslationManager, TrContext
from ..core.version import get_version
from ..core.updater import AppUpdater
from ..gui.theme_language_dialog import ThemeLanguageSelectionDialog
from ..gui.update_dialog import UpdateDialog, UpdateCheckWorker
from ..core.onedrive_manager import OneDriveManager
from ..core.system_info import get_timezone, get_location
from ..core.utils import check_internet_connection
from .tour_guide import TourManager
from .toast import ToastOverlay
from datetime import datetime, timedelta
from .ui_styles import primary_button_style

logger = setup_logger("MainWindow")


class DeviceScanWorker(QThread):
    """Worker thread for device scanning to prevent UI freezing."""
    scan_finished = Signal(list)

    def __init__(self, device_detector):
        super().__init__()
        self.device_detector = device_detector

    def run(self):
        devices = self.device_detector.detect_devices()
        self.scan_finished.emit(devices)


class WorkerThread(QThread):
    """Worker thread for background operations."""
    succeeded = Signal()
    error = Signal(str)
    device_connected = Signal(object)  # Device object
    device_disconnected = Signal(object)  # Device object
    
    def __init__(self, task, *args, **kwargs):
        super().__init__()
        self.task = task
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            self.task(*self.args, **self.kwargs)
            self.succeeded.emit()
        except Exception as e:
            self.error.emit(str(e))


class BadgedButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.badge_count = 0
        self.badge_color = QColor(255, 59, 48) # Red
        self.text_color = QColor(255, 255, 255) # White

    def setBadge(self, count):
        self.badge_count = count
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.badge_count > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Badge dimensions
            size = 14
            rect = self.rect()
            # Position at top-right
            x = rect.width() - size - 2
            y = 2
            
            # Draw circle
            painter.setBrush(QBrush(self.badge_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(x, y, size, size)
            
            # Draw text
            painter.setPen(QPen(self.text_color))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(x, y, size, size, Qt.AlignCenter, str(self.badge_count))

class MainWindow(QMainWindow):
    BUTTON_FONT_PT = 8
    TABLE_FONT_PT = 8
    HEADER_FONT_PT = 8
    COUNTRY_NAMES = {
        "FR": "France",
        "MA": "Morocco",
        "DZ": "Algeria",
        "TN": "Tunisia",
        "EG": "Egypt",
        "US": "United States",
        "GB": "United Kingdom",
        "ES": "Spain",
        "DE": "Germany",
        "IT": "Italy",
        "SA": "Saudi Arabia",
        "AE": "United Arab Emirates",
        "QA": "Qatar",
        "TR": "Turkey",
        "JP": "Japan",
        "CN": "China"
    }
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.config = Config.load_config()
        self.devices = []
        self.device_history = []
        self.last_report_path = None  # Store last generated report path
        self.setup_ui()
        self.uid_loading_dialog = None
        
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        self.theme_manager.theme_changed.connect(self.on_theme_changed)
        try:
            self.on_theme_changed(self.theme_manager.get_current_theme())
        except Exception:
            pass
        
        # Initialize translation manager
        self.translation_manager = TranslationManager()
        
        # Defer heavy service initialization to speed up first paint
        QTimer.singleShot(100, self._init_services)
        
        # Update UI text with current language
        self.update_ui_text()

        # Footer UI: devices count, localized date/time with UTC offset, and location/timezone
        try:
            # Devices count (left-most)
            self.footer_devices_label = QLabel()
            self.footer_clock_label = QLabel()
            self.footer_geo_label = QLabel()
            style = "color: #888; font-size: 11px;"
            self.footer_devices_label.setStyleSheet(style)
            self.footer_clock_label.setStyleSheet(style)
            self.footer_geo_label.setStyleSheet(style)

            # Initial render
            self._update_footer_devices()
            self._update_footer_clock()
            self.footer_geo_label.setText(self._format_footer_geo())

            # Show devices count in status bar (left-most)
            self.footer_devices_label.setVisible(True)
            sb = self._sb()
            sb.addPermanentWidget(self.footer_devices_label)
            sb.addPermanentWidget(self.footer_clock_label)
            sb.addPermanentWidget(self.footer_geo_label)

            # Update clock every second
            self._clock_timer = QTimer(self)
            self._clock_timer.setInterval(1000)
            self._clock_timer.timeout.connect(self._update_footer_clock)
            self._clock_timer.start()
        except Exception as e:
            logger.warning(f"Failed to initialize improved footer UI: {e}")
        
        # Language selector removed from status bar per request

        self.onedrive_status_label = QLabel()
        sb = self._sb()
        sb.addPermanentWidget(self.onedrive_status_label)
        self._update_onedrive_status_indicator()
        
        # Check for first run tour
        QTimer.singleShot(1500, self.check_first_run_tour)

        # Auto-detect devices on startup (after services ready)
        # QTimer.singleShot(600, self.refresh_devices)
        
        # Check for first run
        if Config.is_first_run():
            self.show_first_run_dialog()

        # Initialize Toast Overlay
        self.toast = ToastOverlay(self)

        # Auto-check for updates (silent)
        QTimer.singleShot(2000, self.check_for_updates_background)

        # Initialize background email queue processor
        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_email_queue)
        self.queue_timer.start(60000)  # Check every 60 seconds
        
        # Trigger initial queue check shortly after startup
        QTimer.singleShot(5000, self.process_email_queue)

    def _init_services(self):
        try:
            self.device_detector = DeviceDetector()
            self.report_generator = ReportGenerator()
            self.email_sender = EmailSender()
            self.firmware_flasher = FirmwareFlasher()
            self.onedrive_manager = OneDriveManager()
            self.app_updater = AppUpdater()
            try:
                self.device_detector.start_real_time_monitoring(self._device_change_callback)
            except Exception:
                pass
            try:
                self._update_onedrive_status_indicator()
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Service initialization deferred error: {e}")
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle(QCoreApplication.translate("MainWindow", "AWG Kumulus Device Manager v1.0.0"))
        try:
            self.setWindowIcon(self._icon("logo.png"))
        except Exception:
            pass
            
        self.setMinimumSize(1024, 600)
        from PySide6.QtWidgets import QApplication
        _screen_rect = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(_screen_rect)
        
        # Center window on screen
        self.center_window()
        
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Device list
        left_panel = self.create_device_panel()
        # Reduce minimum width to allow more flexibility
        left_panel.setMinimumWidth(350)
        splitter.addWidget(left_panel)
        
        # Right panel - Controls
        right_panel = self.create_control_panel()
        # Reduce minimum width to allow more flexibility
        right_panel.setMinimumWidth(350)
        splitter.addWidget(right_panel)
        
        # Set splitter proportions (approx 60% / 40%)
        splitter.setSizes([700, 450])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                width: 2px;
                margin: 4px;
            }
            QSplitter::handle:hover {
                background-color: #b0b0b0;
            }
        """)
        
        # Keyboard shortcuts (no toolbar)
        try:
            QShortcut(QKeySequence.Refresh, self, activated=self.refresh_devices)
            QShortcut(QKeySequence("F5"), self, activated=self.refresh_devices)
            QShortcut(QKeySequence("Ctrl+R"), self, activated=self.refresh_devices)
            QShortcut(QKeySequence("Ctrl+G"), self, activated=self.generate_report)
            QShortcut(QKeySequence("Ctrl+E"), self, activated=self.send_email)
            QShortcut(QKeySequence("Ctrl+F"), self, activated=self.flash_firmware_dialog)
            QShortcut(QKeySequence("Ctrl+K"), self, activated=self.show_device_search_dialog)
            
            # New shortcuts
            QShortcut(QKeySequence("Ctrl+U"), self, activated=self.read_uid_dialog)
            QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_stm32_project_dialog)
            QShortcut(QKeySequence("Ctrl+S"), self, activated=self.show_settings_menu)
            QShortcut(QKeySequence("F1"), self, activated=self.show_shortcuts_help)
        except Exception:
            pass

        # Status bar
        self._show_status(QCoreApplication.translate("MainWindow", "Ready"))
        
        # Initialize Tour Manager
        self.tour_manager = TourManager(self)
    
    def closeEvent(self, event):
        """Handle application close event."""
        # Check for pending emails if offline
        try:
            if hasattr(self, 'email_sender') and hasattr(self.email_sender, 'queue_manager'):
                pending = self.email_sender.queue_manager.get_pending_emails()
                if pending and not check_internet_connection():
                    reply = QMessageBox.question(
                        self,
                        QCoreApplication.translate("MainWindow", "Unsent Emails"),
                        QCoreApplication.translate("MainWindow", 
                            "You have {count} unsent emails and no internet connection.\n"
                            "These emails are saved and will be sent automatically when you restart the app with an internet connection.\n\n"
                            "Do you want to close the application now?"
                        ).format(count=len(pending)),
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply == QMessageBox.No:
                        event.ignore()
                        return

        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")
            
        super().closeEvent(event)

    def create_device_panel(self):
        """Create the device list panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel(QCoreApplication.translate("MainWindow", "Connected Devices"))
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)
        
        # Filters
        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(QCoreApplication.translate("MainWindow", "Filter devices"))
        self.filter_input.textChanged.connect(self.apply_device_filter)
        filter_layout.addWidget(self.filter_input)
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItem(QCoreApplication.translate("MainWindow", "All"))
        self.filter_type_combo.currentTextChanged.connect(self.apply_device_filter)
        filter_layout.addWidget(self.filter_type_combo)
        layout.addLayout(filter_layout)

        # Device table
        self.device_table = QTableWidget()
        # Columns: [checkbox], Port, Type, UID, Firmware, Status, Last Seen
        self.device_table.setColumnCount(7)
        self.device_table.setHorizontalHeaderLabels([
            "",
            QCoreApplication.translate("MainWindow", "Port"),
            QCoreApplication.translate("MainWindow", "Type"),
            QCoreApplication.translate("MainWindow", "UID"),
            QCoreApplication.translate("MainWindow", "Firmware"),
            QCoreApplication.translate("MainWindow", "Status"),
            QCoreApplication.translate("MainWindow", "Last Seen"),
        ])
        # Header resize modes per column
        header = self.device_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.device_table.setColumnWidth(0, 30) # Checkbox column
        header.setSectionResizeMode(1, QHeaderView.Interactive) # Port
        header.setSectionResizeMode(2, QHeaderView.Interactive) # Type
        header.setSectionResizeMode(3, QHeaderView.Stretch)     # UID gets remaining space
        header.setSectionResizeMode(4, QHeaderView.Interactive) # Firmware
        header.setSectionResizeMode(5, QHeaderView.Interactive) # Status
        header.setSectionResizeMode(6, QHeaderView.Interactive) # Last Seen
        
        # Set default reasonable widths for interactive columns
        self.device_table.setColumnWidth(1, 80)  # Port
        self.device_table.setColumnWidth(2, 80)  # Type
        self.device_table.setColumnWidth(4, 100) # Firmware
        self.device_table.setColumnWidth(5, 100) # Status
        self.device_table.setColumnWidth(6, 120) # Last Seen
        # Fonts
        self._apply_table_fonts()
        self._apply_table_fonts()
        # Grid lines and readable selection colors
        self.device_table.setStyleSheet(
            "QTableWidget{gridline-color:#6b7a8f;}"
            "QTableWidget::item{padding:6px;}"
            "QHeaderView::section{padding:8px;border:1px solid #4a5568;background:#1f2937;color:#e5e7eb;}"
            "QTableWidget::item:selected{background:#2e3b4f;color:#ffffff;}"
            "QTableWidget::indicator{width:18px;height:18px;}"
            "QTableWidget::indicator:unchecked{background:#e5e7eb;border:1px solid #94a3b8;}"
            "QTableWidget::indicator:checked{background:#3b82f6;border:1px solid #3b82f6;}"
        )
        self.device_table.setAlternatingRowColors(True)
        try:
            self.device_table.verticalHeader().setDefaultSectionSize(34)
        except Exception:
            pass
        # Selection and interactions
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setSelectionMode(QTableWidget.SingleSelection)
        self.device_table.setSortingEnabled(True)
        try:
            from PySide6.QtWidgets import QStyledItemDelegate
            # Keep chip-style delegate for Status column only (column 5)
            self.device_table.setItemDelegateForColumn(5, ChipDelegate(self.device_table))
        except Exception:
            pass
        # Enable context menu for device customization
        self.device_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.device_table.customContextMenuRequested.connect(self.show_device_context_menu)
        # Connect signals as requested
        self.device_table.itemSelectionChanged.connect(self.on_device_selected)
        self.device_table.cellClicked.connect(self.on_device_table_cell_clicked)
        # Keep checkbox change handling
        self.device_table.itemChanged.connect(self._on_device_table_item_changed)
        layout.addWidget(self.device_table)

        # Detailed info panel under the table
        self.device_details_group = self._build_device_details_group()
        layout.addWidget(self.device_details_group)
        
        # Buttons moved under Machine Information section (control panel)
        
        return panel
    
    def show_settings_menu(self):
        """Show the settings menu in a popup dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate('MainWindow', 'Settings'))
        dialog.setMinimumWidth(300)
        dialog.setObjectName("settings_menu_dialog")
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Helper to create styled buttons
        def create_btn(text, icon_name, slot, obj_name=None):
            btn = QPushButton(text)
            btn.setMinimumHeight(44)
            btn.setStyleSheet(primary_button_style())
            if obj_name:
                btn.setObjectName(obj_name)
            # Apply font (assuming _apply_button_font exists or just standard)
            try:
                btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
            except: pass
            
            try:
                btn.setIcon(self._icon(icon_name))
                btn.setIconSize(QSize(24, 24))
            except: pass
            
            btn.clicked.connect(slot)
            btn.clicked.connect(dialog.accept) # Close dialog on click
            return btn

        # Config Button
        btn_config = create_btn(
            QCoreApplication.translate('Settings', 'Config'),
            "settings.png",
            self.show_protected_config_dialog,
            "settings_config_btn"
        )
        layout.addWidget(btn_config)
        
        # Machine Types Button
        btn_machine = create_btn(
            QCoreApplication.translate('Settings', 'Machine Configuration'),
            "washing-machine.png",
            self.configure_machine_types_dialog,
            "settings_machine_btn"
        )
        layout.addWidget(btn_machine)
        
        # Themes Button
        btn_theme = create_btn(
            QCoreApplication.translate('MainWindow', 'Themes & Language'),
            "theme.png",
            self.show_theme_language_dialog,
            "settings_theme_btn"
        )
        layout.addWidget(btn_theme)
        
        # Initialize App Data (First Run)
        btn_init = create_btn(
            QCoreApplication.translate('Settings', 'Initialize App Data'),
            "database.png",
            self.initialize_app_data
        )
        layout.addWidget(btn_init)
        
        # Close Button
        btn_close = QPushButton(QCoreApplication.translate('Dialogs', 'Close'))
        btn_close.clicked.connect(dialog.reject)
        layout.addWidget(btn_close)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def initialize_app_data(self):
        """Initialize app data directories and default configuration for first-time use."""
        try:
            manager = BootstrapManager()
            success, warnings = manager.run_first_run_setup()
            
            # Ensure config keys exist and set safe defaults
            cfg = Config.load_config()
            cfg.setdefault('operator', {'name': '', 'email': '', 'family_name': '', 'phone': '', 'country': ''})
            cfg.setdefault('client_name', '')
            cfg.setdefault('recipients', [])
            cfg.setdefault('machine_types', Config.get_machine_types(cfg))
            cfg.setdefault('machine_type', cfg.get('machine_type', 'Amphore'))
            cfg.setdefault('machine_id', '')
            cfg.setdefault('machine_id_suffix', '')
            cfg.setdefault('onedrive', {
                'enabled': False, 'folder_path': '', 'user_folder': '',
                'sync_enabled': True, 'auto_create_folders': True
            })
            # Persist
            Config.save_config(cfg)
            self.config = cfg
            
            # Inform user and suggest next steps
            msg = QCoreApplication.translate('Dialogs', 'App data initialized successfully.')
            if warnings:
                msg += "\n\n" + QCoreApplication.translate('Dialogs', 'Warnings:') + "\n" + "\n".join(warnings)
            QMessageBox.information(self, QCoreApplication.translate('Dialogs', 'Initialization'), msg)
            
            # Offer quick tour
            try:
                self.show_quick_tour_dialog()
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, QCoreApplication.translate('Dialogs', 'Error'), str(e))

    def show_shortcuts_help(self):
        """Show a dialog with available keyboard shortcuts."""
        shortcuts = [
            ("F5 / Ctrl+R", QCoreApplication.translate("MainWindow", "Refresh Device List")),
            ("Ctrl+F", QCoreApplication.translate("MainWindow", "Flash Firmware")),
            ("Ctrl+U", QCoreApplication.translate("MainWindow", "Read Device UID")),
            ("Ctrl+O", QCoreApplication.translate("MainWindow", "Open STM32 Project")),
            ("Ctrl+S", QCoreApplication.translate("MainWindow", "Open Settings")),
            ("Ctrl+K", QCoreApplication.translate("MainWindow", "Search Devices")),
            ("Ctrl+G", QCoreApplication.translate("MainWindow", "Generate Report")),
            ("Ctrl+E", QCoreApplication.translate("MainWindow", "Send Email")),
            ("F1", QCoreApplication.translate("MainWindow", "Show Shortcuts Help")),
        ]
        
        # Build a nice HTML table for the message
        msg = "<h3>" + QCoreApplication.translate("MainWindow", "Keyboard Shortcuts") + "</h3>"
        msg += "<table width='100%'>"
        for key, desc in shortcuts:
            msg += f"<tr><td style='font-weight:bold; padding-right: 20px;'>{key}</td><td>{desc}</td></tr>"
        msg += "</table>"
            
        QMessageBox.information(self, QCoreApplication.translate("MainWindow", "Keyboard Shortcuts"), msg)

    def check_for_updates(self):
        """Check for application updates (interactive)."""
        try:
            current_version, _ = get_version()
            
            # Use cached result if available
            cached = getattr(self, '_cached_update_result', None)
            
            dialog = UpdateDialog(self, self.app_updater, current_version, cached_result=cached)
            dialog.exec()
            
            # Clear badge after checking/updating if dialog was closed without updating
            # But if they just closed it, maybe we should keep the badge?
            # User said "add to the check for update button ... a littel number 1".
            # Usually the badge clears after you view the update or update it.
            # I'll clear it if they open the dialog, assuming they saw it.
            if hasattr(self, 'btn_update_icon') and isinstance(self.btn_update_icon, BadgedButton):
                self.btn_update_icon.setBadge(0)
            
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            QMessageBox.critical(self, QCoreApplication.translate("MainWindow", "Error"), 
                               QCoreApplication.translate("MainWindow", "Failed to check for updates.") + f"\n{e}")

    def check_for_updates_background(self):
        """Check for application updates silently."""
        try:
            current_version, _ = get_version()
            self._update_worker = UpdateCheckWorker(self.app_updater, current_version)
            self._update_worker.finished.connect(self.on_auto_update_check_finished)
            self._update_worker.start()
        except Exception as e:
            logger.error(f"Failed to start background update check: {e}")

    def on_auto_update_check_finished(self, result):
        """Handle background update check result."""
        try:
            if result:
                # Update found! 
                # Show badge
                if hasattr(self, 'btn_update_icon') and isinstance(self.btn_update_icon, BadgedButton):
                    self.btn_update_icon.setBadge(1)
                
                # Notify user
                new_ver = result.get('version', 'unknown')
                self.toast.show_message(
                    QCoreApplication.translate("MainWindow", "Update Available"),
                    QCoreApplication.translate("MainWindow", "Version {} is available.").format(new_ver),
                    duration=5000,
                    icon_type="info"
                )
                
                # Cache result
                self._cached_update_result = result
            else:
                # No update found
                if hasattr(self, 'btn_update_icon') and isinstance(self.btn_update_icon, BadgedButton):
                    self.btn_update_icon.setBadge(0)
                self._cached_update_result = None
        except Exception as e:
            logger.error(f"Error handling update check result: {e}")

    def create_control_panel(self):
        """Create the control panel."""
        # Create a scroll area to prevent cutting off content on smaller screens
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        layout.setSpacing(20)  # Add more space between main sections
        layout.setContentsMargins(10, 10, 20, 10) # Add right margin for scrollbar
        
        # Operator info group
        op_group = QGroupBox(QCoreApplication.translate("MainWindow", "Operator Information"))
        op_layout = QVBoxLayout()
        op_layout.setSpacing(8)
        op_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header row: Icons only (aligned right)
        header_row = QHBoxLayout()
        header_row.addStretch(1)
        
        self.btn_manual_icon = QPushButton()
        try:
            self.btn_manual_icon.setIcon(self._icon("user-guide.png"))
            self.btn_manual_icon.setIconSize(QSize(20, 20))
        except Exception:
            pass
        self.btn_manual_icon.setToolTip(QCoreApplication.translate("MainWindow", "UserManual"))
        self.btn_manual_icon.clicked.connect(self.open_user_manual_current_lang)
        self.btn_manual_icon.setFixedSize(QSize(32, 32))
        header_row.addWidget(self.btn_manual_icon)
        
        self.btn_support_icon = QPushButton()
        try:
            self.btn_support_icon.setIcon(self._icon("customer-service.png"))
            self.btn_support_icon.setIconSize(QSize(20, 20))
        except Exception:
            pass
        self.btn_support_icon.setToolTip(QCoreApplication.translate("MainWindow", "Support"))
        self.btn_support_icon.clicked.connect(self.show_contact_support_dialog)
        self.btn_support_icon.setFixedSize(QSize(32, 32))
        header_row.addWidget(self.btn_support_icon)
        
        self.btn_tour_icon = QPushButton()
        try:
            self.btn_tour_icon.setIcon(self._icon("Quicktour.png"))
            self.btn_tour_icon.setIconSize(QSize(20, 20))
        except Exception:
            pass
        self.btn_tour_icon.setToolTip(QCoreApplication.translate("MainWindow", "Quick Tour"))
        self.btn_tour_icon.clicked.connect(self.show_quick_tour_dialog)
        self.btn_tour_icon.setFixedSize(QSize(32, 32))
        header_row.addWidget(self.btn_tour_icon)
        
        self.btn_update_icon = BadgedButton()
        try:
            self.btn_update_icon.setIcon(self._icon("update.png"))
            self.btn_update_icon.setIconSize(QSize(20, 20))
        except Exception:
            pass
        self.btn_update_icon.setToolTip(QCoreApplication.translate("MainWindow", "Check for Updates"))
        self.btn_update_icon.setObjectName("btn_check_updates")
        self.btn_update_icon.clicked.connect(self.check_for_updates)
        self.btn_update_icon.setFixedSize(QSize(32, 32))
        header_row.addWidget(self.btn_update_icon)
        
        op_layout.addLayout(header_row)

        # Form layout for fields
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        
        self.operator_name = QLineEdit()
        self.operator_name.setText(self.config.get('operator', {}).get('name', ''))
        self.operator_name.setMinimumHeight(32)
        self.operator_name.setStyleSheet("QLineEdit { padding: 4px; }")
        form_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Full name:")), self.operator_name)
        
        self.operator_email = QLineEdit()
        self.operator_email.setText(self.config.get('operator', {}).get('email', ''))
        self.operator_email.setMinimumHeight(32)
        self.operator_email.setStyleSheet("QLineEdit { padding: 4px; }")
        form_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Email:")), self.operator_email)
        
        self.operator_phone = QLineEdit()
        self.operator_phone.setPlaceholderText("+212 6 12 34 56 78")
        self.operator_phone.setText(self.config.get('operator', {}).get('phone', ''))
        self.operator_phone.setMinimumHeight(32)
        self.operator_phone.setStyleSheet("QLineEdit { padding: 4px; }")
        form_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Phone Number:")), self.operator_phone)
        
        self.operator_country = QLineEdit()
        try:
            _det = self._get_detected_country_from_footer()
            if not _det:
                _det = self._detect_country_name()
        except Exception:
            _det = ""
        self.operator_country.setText(self.config.get('operator', {}).get('country', _det))
        self.operator_country.setMinimumHeight(32)
        self.operator_country.setStyleSheet("QLineEdit { padding: 4px; }")
        form_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Pays:")), self.operator_country)
        
        op_layout.addLayout(form_layout)
        
        op_group.setLayout(op_layout)
        op_group.setMaximumWidth(800)
        layout.addWidget(op_group)

        auto_group = QGroupBox(QCoreApplication.translate("MainWindow", "Auto Flash"))

        auto_layout = QVBoxLayout()
        self.auto_flash_enabled = QCheckBox(QCoreApplication.translate("MainWindow", "Enable Auto-Flash on Connect"))
        self.auto_flash_enabled.setChecked(self.config.get('auto_flash', {}).get('enabled', False))
        auto_layout.addWidget(self.auto_flash_enabled)
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Firmware .bin Path:")))
        self.auto_flash_path = QLineEdit()
        self.auto_flash_path.setText(self.config.get('auto_flash', {}).get('firmware_path', ''))
        path_row.addWidget(self.auto_flash_path)
        browse_btn = QPushButton(QCoreApplication.translate("MainWindow", "Browse"))
        browse_btn.clicked.connect(self._browse_auto_flash_firmware)
        path_row.addWidget(browse_btn)
        auto_layout.addLayout(path_row)
        types_row = QHBoxLayout()
        types_row.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Boards:")))
        allowed = set(self.config.get('auto_flash', {}).get('board_types', []) or [])
        self.auto_flash_stm32 = QCheckBox("STM32")
        self.auto_flash_stm32.setChecked('STM32' in allowed)
        types_row.addWidget(self.auto_flash_stm32)
        auto_layout.addLayout(types_row)
        save_btn = QPushButton(QCoreApplication.translate("MainWindow", "Save Auto-Flash Settings"))
        save_btn.clicked.connect(self._save_auto_flash_config)
        auto_layout.addWidget(save_btn)
        auto_group.setLayout(auto_layout)
        auto_group.setMaximumWidth(800)
        auto_group.setVisible(False)  # Hidden per request
        layout.addWidget(auto_group)
        
        # Machine info group
        machine_group = QGroupBox(QCoreApplication.translate("MainWindow", "Machine Information"))
        machine_layout = QVBoxLayout()
        machine_form = QFormLayout()
        machine_form.setContentsMargins(0, 0, 0, 0)
        
        self.client_name = QLineEdit()
        self.client_name.setText(self.config.get('client_name', ''))
        self.client_name.setPlaceholderText(QCoreApplication.translate("MainWindow", "Enter client name"))
        self.client_name.textChanged.connect(self._save_client_name)
        machine_form.addRow(QLabel(QCoreApplication.translate("MainWindow", "Client Name:")), self.client_name)

        self.machine_type = QComboBox()
        self.update_machine_type_combo()
        machine_type_idx = list(Config.get_machine_types(self.config).keys()).index(
            self.config.get('machine_type', 'Amphore')
        )
        self.machine_type.setCurrentIndex(machine_type_idx)
        self.machine_type.currentTextChanged.connect(self.on_machine_type_changed)
        machine_form.addRow(QLabel(QCoreApplication.translate("MainWindow", "Machine Type:")), self.machine_type)
        
        # Machine ID composed of prefix + numeric suffix
        # Read-only field showing the composed ID
        self.machine_id = QLineEdit()
        self.machine_id.setReadOnly(True)
        self.machine_id.setPlaceholderText(QCoreApplication.translate("MainWindow", "Enter machine ID"))
        machine_form.addRow(QLabel(QCoreApplication.translate("MainWindow", "Machine ID:")), self.machine_id)

        # Display the current prefix and provide an editable suffix dropdown
        self.machine_id_prefix_display = QLabel("-")
        self.machine_id_prefix_display.setStyleSheet("font-family: monospace; font-weight: bold;")
        machine_form.addRow(QLabel(QCoreApplication.translate("MainWindow", "ID Prefix:")), self.machine_id_prefix_display)

        self.machine_id_suffix = QComboBox()
        self.machine_id_suffix.setEditable(True)
        self.machine_id_suffix.setInsertPolicy(QComboBox.NoInsert)
        # Update composed ID whenever the suffix changes
        self.machine_id_suffix.editTextChanged.connect(self.on_machine_id_suffix_changed)
        self.machine_id_suffix.currentTextChanged.connect(self.on_machine_id_suffix_changed)
        machine_form.addRow(QLabel(QCoreApplication.translate("MainWindow", "ID Suffix:")), self.machine_id_suffix)
        
        machine_layout.addLayout(machine_form)

        # Initialize ID widgets for the current machine type
        self.on_machine_type_changed(self.machine_type.currentText())
        # Load persisted machine ID/suffix if available
        try:
            saved_id = self.config.get('machine_id', '')
            saved_suffix = self.config.get('machine_id_suffix', '')
            prefix = self.machine_id_prefix_display.text()
            if saved_id and saved_id.startswith(prefix):
                # Derive suffix from saved ID
                suffix = saved_id[len(prefix):]
                self.machine_id_suffix.setEditText(suffix)
                self.machine_id.setText(saved_id)
            elif saved_suffix:
                self.machine_id_suffix.setEditText(saved_suffix)
                if prefix:
                    self.machine_id.setText(prefix + saved_suffix)
        except Exception:
            pass
        
        machine_group.setLayout(machine_layout)
        machine_group.setMaximumWidth(800)
        layout.addWidget(machine_group)

        # Action buttons (spread across full width, under Machine Information)
        button_container = QWidget()
        button_container.setMaximumWidth(800)
        button_layout = QGridLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)

        # Row 0: Refresh, History
        # Refresh Devices
        refresh_btn = QPushButton(QCoreApplication.translate('MainWindow', 'Refresh Devices'))
        refresh_btn.setToolTip(QCoreApplication.translate('MainWindow', 'Refresh Device List (Ctrl+R)'))
        refresh_btn.clicked.connect(self.refresh_devices)
        refresh_btn.setStyleSheet(primary_button_style())
        self._apply_button_font(refresh_btn)
        refresh_btn.setMinimumHeight(44)
        try:
            refresh_btn.setIcon(self._icon("rotation.png"))
            refresh_btn.setIconSize(QSize(20, 20))
        except Exception:
            pass
        refresh_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_layout.addWidget(refresh_btn, 0, 0)
        self.refresh_btn = refresh_btn  # Store as instance variable for translation

        # Device History
        history_btn = QPushButton(QCoreApplication.translate('MainWindow', 'Device History'))
        history_btn.clicked.connect(self.show_device_history_dialog)
        history_btn.setStyleSheet(primary_button_style())
        self._apply_button_font(history_btn)
        history_btn.setMinimumHeight(44)
        try:
            history_btn.setIcon(self._icon("history.png"))
            history_btn.setIconSize(QSize(20, 20))
        except Exception:
            pass
        history_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_layout.addWidget(history_btn, 0, 1)
        self.history_btn = history_btn  # Store as instance variable for translation
        
        # Row 1: Email, Flash
        email_btn = QPushButton(QCoreApplication.translate('MainWindow', 'Send Email'))
        email_btn.setToolTip(QCoreApplication.translate('MainWindow', 'Send Email Report (Ctrl+E)'))
        email_btn.clicked.connect(self.send_email)
        email_btn.setStyleSheet(primary_button_style())
        self._apply_button_font(email_btn)
        email_btn.setMinimumHeight(44)
        try:
            email_btn.setIcon(self._icon("mail.png"))
            email_btn.setIconSize(QSize(20, 20))
        except Exception:
            pass
        email_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_layout.addWidget(email_btn, 1, 0)
        self.email_btn = email_btn  # Store as instance variable for translation
        
        flash_btn = QPushButton(QCoreApplication.translate('MainWindow', 'Flash Firmware'))
        flash_btn.setObjectName("flash_btn")
        flash_btn.setToolTip(QCoreApplication.translate('MainWindow', 'Flash Firmware (Ctrl+F)'))
        flash_btn.clicked.connect(self.flash_firmware_dialog)
        flash_btn.setStyleSheet(primary_button_style())
        self._apply_button_font(flash_btn)
        flash_btn.setMinimumHeight(44)
        try:
            flash_btn.setIcon(self._icon("flash.png"))
            flash_btn.setIconSize(QSize(20, 20))
        except Exception:
            pass
        flash_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_layout.addWidget(flash_btn, 1, 1)
        self.flash_btn = flash_btn  # Store as instance variable for translation

        # Row 2: Read UID, Open Proj
        # Read UID
        read_uid_btn = QPushButton(QCoreApplication.translate('MainWindow', 'Read UID'))
        read_uid_btn.setObjectName("read_uid_btn")
        read_uid_btn.setToolTip(QCoreApplication.translate('MainWindow', 'Read Device UID (Ctrl+U)'))
        read_uid_btn.clicked.connect(self.read_uid_dialog)
        read_uid_btn.setStyleSheet(primary_button_style())
        self._apply_button_font(read_uid_btn)
        read_uid_btn.setMinimumHeight(44)
        try:
            read_uid_btn.setIcon(self._icon("search.png"))  # reusing search icon or any other
            read_uid_btn.setIconSize(QSize(20, 20))
        except Exception:
            pass
        read_uid_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_layout.addWidget(read_uid_btn, 2, 0)
        self.read_uid_btn = read_uid_btn

        # Open STM32 Project
        open_stm32_btn = QPushButton(QCoreApplication.translate('MainWindow', 'OpenProj'))
        open_stm32_btn.setObjectName("open_stm32_btn")
        open_stm32_btn.setToolTip(QCoreApplication.translate('MainWindow', 'Open STM32 Project (Ctrl+O)'))
        open_stm32_btn.clicked.connect(self.open_stm32_project_dialog)
        open_stm32_btn.setStyleSheet(primary_button_style())
        self._apply_button_font(open_stm32_btn)
        open_stm32_btn.setMinimumHeight(44)
        try:
            open_stm32_btn.setIcon(self._icon("source-code.png"))
            open_stm32_btn.setIconSize(QSize(20, 20))
        except Exception:
            pass
        open_stm32_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_layout.addWidget(open_stm32_btn, 2, 1)
        self.open_stm32_btn = open_stm32_btn  # Store for translation

        # Row 3: Settings
        settings_btn = QPushButton(QCoreApplication.translate('MainWindow', 'Settings'))
        settings_btn.setObjectName("settings_btn")
        settings_btn.setToolTip(QCoreApplication.translate('MainWindow', 'Open Settings (Ctrl+S)'))
        settings_btn.clicked.connect(self.show_settings_menu)
        settings_btn.setStyleSheet(primary_button_style())
        self._apply_button_font(settings_btn)
        settings_btn.setMinimumHeight(44)
        try:
            settings_btn.setIcon(self._icon("setting.png"))
            settings_btn.setIconSize(QSize(20, 20))
        except Exception:
            pass
        settings_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_layout.addWidget(settings_btn, 3, 0)
        self.settings_btn = settings_btn
        
        # Ensure columns are equal width
        button_layout.setColumnStretch(0, 1)
        button_layout.setColumnStretch(1, 1)

        layout.addWidget(button_container)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(800)
        layout.addWidget(self.progress_bar)
        
        # Logs section removed per request
        
        scroll_area.setWidget(panel)
        return scroll_area

    def _browse_auto_flash_firmware(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("MainWindow", "Select Firmware File"),
            "",
            "Firmware Files (*.bin);;All Files (*)"
        )
        if file_path:
            self.auto_flash_path.setText(file_path)

    def _save_auto_flash_config(self):
        cfg = self.config
        af = cfg.get('auto_flash', {})
        af['enabled'] = self.auto_flash_enabled.isChecked()
        af['firmware_path'] = self.auto_flash_path.text().strip()
        types = []
        if self.auto_flash_stm32.isChecked():
            types.append('STM32')
        af['board_types'] = types
        cfg['auto_flash'] = af
        try:
            from src.core.config import Config as _C
            _C.save_config(cfg)
            self._show_status(QCoreApplication.translate("MainWindow", "Auto-Flash settings saved"))
        except Exception:
            pass

    def _icon(self, filename: str) -> QIcon:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
             base = Path(sys._MEIPASS)
             p = base / "src" / "assets" / filename
        else:
             p = Path(__file__).resolve().parent.parent / "assets" / filename
        return QIcon(str(p))
    
    def refresh_devices(self):
        """Refresh the device list."""
        if hasattr(self, 'scan_worker') and self.scan_worker and self.scan_worker.isRunning():
            logger.info("Scan already in progress, queuing next scan")
            self._pending_refresh = True
            return

        self._show_status(QCoreApplication.translate("MainWindow", "Scanning for devices..."))
        
        # Disable refresh button
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.setEnabled(False)
            self.refresh_btn.setText(QCoreApplication.translate("MainWindow", "Scanning..."))
            
        self.scan_worker = DeviceScanWorker(self.device_detector)
        self.scan_worker.scan_finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_scan_finished(self, devices):
        """Handle scan completion."""
        self.devices = devices
        self.filtered_devices = list(self.devices)
        try:
            types = sorted({d.board_type.value for d in self.devices})
            self.filter_type_combo.blockSignals(True)
            self.filter_type_combo.clear()
            self.filter_type_combo.addItem(QCoreApplication.translate("MainWindow", "All"))
            for t in types:
                self.filter_type_combo.addItem(t)
            self.filter_type_combo.blockSignals(False)
        except Exception:
            pass
        self.update_device_table()
        self._show_status(QCoreApplication.translate("MainWindow", "Found {count} device(s)").format(count=len(self.devices)))
        try:
            self._update_footer_devices()
        except Exception:
            pass
            
        # Re-enable refresh button
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText(QCoreApplication.translate('MainWindow', 'Refresh Devices'))

        # Check for pending refresh
        if getattr(self, '_pending_refresh', False):
            self._pending_refresh = False
            QTimer.singleShot(100, self.refresh_devices)

        # Auto-generate report when inputs are ready (silent)
        try:
            QTimer.singleShot(50, self.auto_generate_report_if_ready)
        except Exception:
            pass
    
    def update_device_table(self):
        """Update the device table with current devices."""
        devices = getattr(self, 'filtered_devices', self.devices)
        self.device_table.setRowCount(len(devices))
        
        for row, device in enumerate(devices):
            # Load UID checkbox
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Unchecked)
            checkbox_item.setToolTip(QCoreApplication.translate("MainWindow", "Check to load UID from board"))
            self.device_table.setItem(row, 0, checkbox_item)

            # Port
            it = QTableWidgetItem(device.port)
            it.setToolTip(QCoreApplication.translate("MainWindow", "Click to copy. Right-click for options."))
            self.device_table.setItem(row, 1, it)
            
            # Type
            board_type = device.board_type.value
            it = QTableWidgetItem(board_type)
            it.setToolTip(QCoreApplication.translate("MainWindow", "Click to copy. Right-click for options."))
            self.device_table.setItem(row, 2, it)

            # UID (column 3)
            uid_val = device.uid
            if not uid_val:
                uid_val = "—"
            it = QTableWidgetItem(str(uid_val))
            it.setToolTip(self._device_details_text(device))
            self.device_table.setItem(row, 3, it)

            # Firmware (column 4)
            fw = getattr(device, 'firmware_version', None) or "-"
            it = QTableWidgetItem(fw)
            it.setToolTip(QCoreApplication.translate("MainWindow", "Click to copy. Right-click for options."))
            self.device_table.setItem(row, 4, it)

            # Status (column 5)
            status_item = QTableWidgetItem(device.status)
            status_item.setToolTip(QCoreApplication.translate("MainWindow", "Click to copy. Right-click for options."))
            self.device_table.setItem(row, 5, status_item)

            # Last Seen (column 6)
            if device.last_seen:
                dt = QDateTime.fromString(device.last_seen, Qt.ISODate)
                if dt.isValid():
                    secs = dt.secsTo(QDateTime.currentDateTime())
                    if secs < 60:
                        ls = QCoreApplication.translate("MainWindow", "Just now")
                    elif secs < 3600:
                        ls = QCoreApplication.translate("MainWindow", "{} min ago").format(secs//60)
                    elif secs < 86400:
                        ls = QCoreApplication.translate("MainWindow", "{} h ago").format(secs//3600)
                    else:
                        ls = dt.date().toString(QLocale().dateFormat(QLocale.ShortFormat))
                else:
                    ls = device.last_seen.split('T')[0]
            else:
                ls = QCoreApplication.translate("MainWindow", "Never")
            # Last Seen (column 6)
            it = QTableWidgetItem(ls)
            it.setToolTip(QCoreApplication.translate("MainWindow", "Click to copy. Right-click for options."))
            self.device_table.setItem(row, 6, it)
        
        if devices:
            current_row = self.device_table.currentRow()
            target_row = current_row if 0 <= current_row < len(devices) else 0
            self.device_table.blockSignals(True)
            self.device_table.selectRow(target_row)
            self.device_table.blockSignals(False)
            self._update_device_details(devices[target_row])
        else:
            self._clear_device_details()
        try:
            self._adjust_layout_density(len(devices))
        except Exception:
            pass

    def _copy_text(self, text: str):
        try:
            QGuiApplication.clipboard().setText(text or "")
            self._show_status(QCoreApplication.translate("MainWindow", "Copied: {text}").format(text=(text or "")[:60]))
        except Exception:
            pass

    def copy_cell_value(self, item: QTableWidgetItem):
        """Copy the clicked cell's text to the clipboard automatically."""
        if not item:
            return
        self._copy_text(item.text())
    
    def _apply_button_font(self, w):
        try:
            f = QFont()
            f.setPointSize(self.BUTTON_FONT_PT)
            w.setFont(f)
        except Exception:
            pass

    def _apply_table_fonts(self):
        try:
            tf = QFont()
            tf.setPointSize(self.TABLE_FONT_PT)
            self.device_table.setFont(tf)
            hf = QFont()
            hf.setPointSize(self.HEADER_FONT_PT)
            hf.setBold(True)
            self.device_table.horizontalHeader().setFont(hf)
        except Exception:
            pass
    def _sb(self):
        try:
            fn = super(MainWindow, self).statusBar
            if callable(fn):
                return fn()
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QStatusBar
            v = getattr(self, 'statusBar', None)
            if isinstance(v, QStatusBar):
                return v
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QStatusBar
            self._status_bar = getattr(self, '_status_bar', None) or QStatusBar(self)
            self.setStatusBar(self._status_bar)
            return self._status_bar
        except Exception:
            return None
    def _show_status(self, text: str):
        sb = self._sb()
        if sb:
            sb.showMessage(text)
    def _device_details_text(self, device: Device) -> str:
        def _fmt_hex(val):
            try:
                if val is None:
                    return None
                if isinstance(val, int):
                    return f"0x{val:04X}"
                s = str(val).strip()
                if s.lower().startswith("0x"):
                    return f"0x{int(s,16):04X}"
                return f"0x{int(s):04X}"
            except Exception:
                return str(val)
        lines = [
            f"{QCoreApplication.translate('MainWindow', 'UID')}: {device.uid or 'N/A'}",
            f"{QCoreApplication.translate('MainWindow', 'Chip ID')}: {device.chip_id or 'N/A'}",
            f"{QCoreApplication.translate('MainWindow', 'MAC')}: {device.mac_address or 'N/A'}",
            f"{QCoreApplication.translate('MainWindow', 'Firmware')}: {device.firmware_version or 'N/A'}",
            f"{QCoreApplication.translate('MainWindow', 'Hardware')}: {device.hardware_version or 'N/A'}",
            f"{QCoreApplication.translate('MainWindow', 'Flash')}: {device.flash_size or 'N/A'}",
            f"{QCoreApplication.translate('MainWindow', 'CPU')}: {device.cpu_frequency or 'N/A'}",
            f"{QCoreApplication.translate('MainWindow', 'Serial')}: {device.serial_number or 'N/A'}",
            f"{QCoreApplication.translate('MainWindow', 'Manufacturer')}: {device.manufacturer or 'N/A'}",
            f"VID:PID: {_fmt_hex(device.vid)}:{_fmt_hex(device.pid)}" if device.vid and device.pid else "VID:PID: N/A",
        ]
        return "\n".join(lines)

    def _build_device_details_group(self) -> QGroupBox:
        group = QGroupBox(QCoreApplication.translate("MainWindow", "Selected Device Details"))
        
        # Scroll area for details
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        form = QFormLayout(content_widget)
        
        self.device_detail_labels = {}
        detail_fields = [
            ("board", QCoreApplication.translate("MainWindow", "Board Type")),
            ("port", QCoreApplication.translate("MainWindow", "Port")),
            ("uid", QCoreApplication.translate("MainWindow", "UID")),
            ("chip_id", QCoreApplication.translate("MainWindow", "Chip ID")),
            ("mac", QCoreApplication.translate("MainWindow", "MAC Address")),
            ("firmware", QCoreApplication.translate("MainWindow", "Firmware Version")),
            ("hardware", QCoreApplication.translate("MainWindow", "Hardware Version")),
            ("flash", QCoreApplication.translate("MainWindow", "Flash Size")),
            ("cpu", QCoreApplication.translate("MainWindow", "CPU Frequency")),
            ("serial", QCoreApplication.translate("MainWindow", "Serial Number")),
            ("vidpid", QCoreApplication.translate("MainWindow", "VID:PID")),
            ("manufacturer", QCoreApplication.translate("MainWindow", "Manufacturer")),
            ("description", QCoreApplication.translate("MainWindow", "Description")),
            ("status", QCoreApplication.translate("MainWindow", "Status")),
            ("health", QCoreApplication.translate("MainWindow", "Health Score")),
            ("first_seen", QCoreApplication.translate("MainWindow", "First Detected")),
            ("last_seen", QCoreApplication.translate("MainWindow", "Last Seen")),
            ("connections", QCoreApplication.translate("MainWindow", "Connections")),
        ]
        for key, label_text in detail_fields:
            value_label = QLabel("—")
            value_label.setObjectName(f"device_detail_{key}")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(QLabel(label_text + ":"), value_label)
            self.device_detail_labels[key] = value_label
            
        self.device_extra_info = QTextEdit()
        self.device_extra_info.setReadOnly(True)
        self.device_extra_info.setPlaceholderText(QCoreApplication.translate("MainWindow", "No additional info yet"))
        self.device_extra_info.setMaximumHeight(140)
        form.addRow(QLabel(QCoreApplication.translate("MainWindow", "Additional Info:")), self.device_extra_info)
        
        scroll.setWidget(content_widget)
        
        layout = QVBoxLayout()
        layout.addWidget(scroll)
        group.setLayout(layout)
        
        return group

    def _clear_device_details(self):
        if not hasattr(self, 'device_detail_labels'):
            return
        for label in self.device_detail_labels.values():
            label.setText("—")
        if hasattr(self, 'device_extra_info'):
            self.device_extra_info.setPlainText(QCoreApplication.translate("MainWindow", "No additional info yet"))

    def _update_device_details(self, device: Optional[Device]):
        if not device or not hasattr(self, 'device_detail_labels'):
            self._clear_device_details()
            return

        def _fmt(value):
            return value if value not in (None, "", "N/A") else "N/A"

        def _fmt_hex(val):
            try:
                if val is None:
                    return None
                if isinstance(val, int):
                    return f"0x{val:04X}"
                s = str(val).strip()
                if s.lower().startswith("0x"):
                    return f"0x{int(s,16):04X}"
                return f"0x{int(s):04X}"
            except Exception:
                return str(val)

        vid = _fmt_hex(getattr(device, 'vid', None))
        pid = _fmt_hex(getattr(device, 'pid', None))
        vidpid = f"{vid}:{pid}" if vid and pid else "N/A"

        details_map = {
            "board": device.board_type.value,
            "port": device.port,
            "uid": device.uid or "N/A",
            "chip_id": device.chip_id or "N/A",
            "mac": device.mac_address or "N/A",
            "firmware": device.firmware_version or "N/A",
            "hardware": device.hardware_version or "N/A",
            "flash": device.flash_size or "N/A",
            "cpu": device.cpu_frequency or "N/A",
            "serial": device.serial_number or "N/A",
            "vidpid": vidpid,
            "manufacturer": device.manufacturer or "N/A",
            "description": device.description or "N/A",
            "status": device.status or "N/A",
            "health": f"{device.health_score}%" if device.health_score is not None else "N/A",
            "first_seen": device.first_detected or "N/A",
            "last_seen": device.last_seen or "N/A",
            "connections": str(device.connection_count),
        }
        for key, value in details_map.items():
            label = self.device_detail_labels.get(key)
            if label:
                label.setText(_fmt(value))

        extra = dict(device.extra_info or {})
        raw_output = extra.pop("raw_output", None)
        lines = []
        for key in sorted(extra.keys()):
            lines.append(f"{key}: {extra[key]}")
        if raw_output:
            lines.append("raw_output:")
            lines.append(raw_output)
        if lines:
            self.device_extra_info.setPlainText("\n".join(lines))
        else:
            self.device_extra_info.setPlainText(QCoreApplication.translate("MainWindow", "No additional info yet"))

    def _on_device_selection_changed(self):
        devices = getattr(self, 'filtered_devices', self.devices)
        row = self.device_table.currentRow()
        if 0 <= row < len(devices):
            device = devices[row]
            self._update_device_details(device)
            # Auto-flash removed as per user request
        else:
            self._clear_device_details()

    def _on_device_table_item_changed(self, item):
        """Handle checkbox changes in device table."""
        if item.column() == 0:  # Load UID checkbox column
            # Visual feedback only: blue background when checked
            try:
                if item.checkState() == Qt.Checked:
                    item.setBackground(QColor("#dbeafe"))  # light blue
                else:
                    item.setBackground(QColor(Qt.transparent))
            except Exception:
                pass

    def on_device_selected(self):
        """Public handler for device selection change (wrapper)."""
        try:
            self._on_device_selection_changed()
        except Exception:
            pass

    def on_device_table_cell_clicked(self, row: int, column: int):
        """Handle cell clicks (wrapper)."""
        try:
            item = self.device_table.item(row, column)
            if item:
                self.copy_cell_value(item)
        except Exception:
            pass

    def _show_uid_loading_overlay(self) -> Optional[QProgressDialog]:
        """Create and display a loading dialog while fetching UID data."""
        try:
            dialog = QProgressDialog(
                QCoreApplication.translate("MainWindow", "Loading the UID of the board... Please wait."),
                None,
                0,
                0,
                self
            )
            dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Loading UID"))
            dialog.setCancelButton(None)
            dialog.setWindowModality(Qt.ApplicationModal)
            dialog.setMinimumDuration(0)
            dialog.setAutoClose(False)
            dialog.show()
            # QApplication.processEvents() # Removed to prevent recursive repaint
            return dialog
        except Exception:
            return None

    def _on_uid_progress(self, msg):
        """Handle progress updates for UID loading dialog."""
        if self.uid_loading_dialog:
            self.uid_loading_dialog.setLabelText(msg)

    def _load_device_uid(self, device: Device, row: int, show_info: bool = True):
        """Load UID by flashing firmware and reading device info (Async)."""
        try:
            # Show loading popup
            self.uid_loading_dialog = self._show_uid_loading_overlay()
            if not self.uid_loading_dialog:
                return

            # Connect progress signal
            try:
                self.firmware_flasher.progress_update.disconnect(self._on_uid_progress)
            except (RuntimeError, TypeError):
                # Ignore if not connected
                pass
            except Exception:
                pass
            self.firmware_flasher.progress_update.connect(self._on_uid_progress)

            # Capture data for thread
            machine_id_text = self.machine_id.text() or ""

            # Start worker
            self.uid_worker = WorkerThread(
                self._load_device_uid_task,
                device,
                machine_id_text
            )
            self.uid_worker.finished.connect(lambda: self._on_uid_load_success(device, row, show_info))
            self.uid_worker.error.connect(lambda err: self._on_uid_load_error(err))
            self.uid_worker.start()

        except Exception as e:
            logger.warning(f"UID loading setup error: {e}")
            if self.uid_loading_dialog:
                self.uid_loading_dialog.close()
            QMessageBox.critical(self, QCoreApplication.translate("MainWindow", "Error"), f"{str(e)}")

    def _ensure_uid_firmware_ready(self, progress_callback) -> Path:
        """Find or download GetMachineUid.bin (Thread-safe, for WorkerThread)."""
        # 1. Search local paths
        candidates = [
            Config.WORKSPACE_DIR / 'GetMachineID' / 'GetMachineUid.bin',
            Path.cwd() / 'BinaryFiles' / 'GetMachineID' / 'GetMachineUid.bin',
            Path.cwd() / 'BinaryFiles' / 'GetMachineUid.bin',
        ]

        # Check bundled resources (PyInstaller)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base = Path(sys._MEIPASS)
            candidates.insert(0, base / 'BinaryFiles' / 'GetMachineID' / 'GetMachineUid.bin')
            candidates.insert(0, base / 'BinaryFiles' / 'GetMachineUid.bin')
        
        # Try to find existing
        for p in candidates:
            try:
                if p.exists() and p.stat().st_size > 1000:
                    return p
            except Exception:
                continue
                
        # 2. Download if not found
        if not check_internet_connection():
            raise Exception(QCoreApplication.translate("MainWindow", "Internet connection required to download firmware. Please connect to the internet."))

        target_file = Config.WORKSPACE_DIR / 'GetMachineID' / 'GetMachineUid.bin'
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            url = Config.GET_MACHINE_UID_URL
            progress_callback(QCoreApplication.translate("MainWindow", "Downloading firmware..."))
            
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            with open(target_file, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded / total * 100)
                            # Only update periodically to avoid spamming signals
                            if pct % 10 == 0: 
                                progress_callback(QCoreApplication.translate("MainWindow", f"Downloading firmware... {pct}%"))
                                
            if target_file.stat().st_size < 1000:
                 raise ValueError("Downloaded file too small")
                 
            return target_file
            
        except Exception as e:
            logger.error(f"Failed to download firmware: {e}")
            if target_file.exists():
                try:
                    target_file.unlink()
                except Exception:
                    pass
            raise Exception(f"Firmware download failed: {str(e)}")

    def _load_device_uid_task(self, device, machine_id_text):
        """Background task for UID loading."""
        # Pause monitoring to avoid conflicts
        if hasattr(self.device_detector, 'pause_monitoring'):
            self.device_detector.pause_monitoring()
            
        try:
            def progress(msg):
                self.firmware_flasher.progress_update.emit(msg)

            # Ensure firmware
            firmware_path = self._ensure_uid_firmware_ready(progress)

            self.firmware_flasher.progress_update.emit(QCoreApplication.translate("MainWindow", "Flashing UID firmware..."))
            
            # Flash
            ok = self.firmware_flasher.flash_firmware(device, str(firmware_path))
            if not ok:
                raise Exception("Firmware flashing failed")
                
            self.firmware_flasher.progress_update.emit(QCoreApplication.translate("MainWindow", "Reading device information..."))
            
            # Read info
            time.sleep(1.0) # Give it a moment to boot
            self.device_detector._read_device_info(device)
            
            # Explicitly read UID if missing (STM32 only)
            if not device.uid and device.board_type == BoardType.STM32:
                self.firmware_flasher.progress_update.emit(QCoreApplication.translate("MainWindow", "Checking boot output for UID..."))
                try:
                    # Attempt to read boot output first (without resetting buffer)
                    with serial.Serial(device.port, 115200, timeout=0.5) as ser:
                        boot_output = ""
                        # Quick read of what's already there
                        if ser.in_waiting:
                            boot_output = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                        
                        # Check for UID
                        if "UID:" in boot_output:
                            for line in boot_output.splitlines():
                                if "UID:" in line:
                                    parts = line.split('UID:')
                                    if len(parts) > 1:
                                        uid_cand = parts[1].strip().split()[0]
                                        uid_cand = uid_cand.replace('0x', '').replace(':', '').upper()
                                        if len(uid_cand) >= 24:
                                            device.uid = uid_cand
                                            break
                except Exception as e:
                    logger.debug(f"Boot output read failed: {e}")

                # If still no UID, try the command method
                if not device.uid:
                    self.firmware_flasher.progress_update.emit(QCoreApplication.translate("MainWindow", "Reading UID directly..."))
                    uid = self.device_detector.read_stm32_uid_direct(device.port)
                    if uid:
                        device.uid = uid

            # Capture all serial output (e.g. boot logs)
            self.firmware_flasher.progress_update.emit(QCoreApplication.translate("MainWindow", "Capturing detailed serial info..."))
            serial_dump = self.device_detector.read_all_serial_output(device.port, timeout=3.0)
            
            # Update device object
            device.extra_info = device.extra_info or {}
            device.extra_info['uid_flashed'] = True
            device.extra_info['machine_id'] = machine_id_text
            device.extra_info['serial_output'] = serial_dump
            
            # Update history
            self.device_detector.update_device_in_history(device)
            
        finally:
            # Resume monitoring
            if hasattr(self.device_detector, 'resume_monitoring'):
                self.device_detector.resume_monitoring()

    def _on_uid_load_success(self, device, row, show_info=True):
        """Handle successful UID load."""
        try:
            try:
                self.firmware_flasher.progress_update.disconnect(self._on_uid_progress)
            except (RuntimeError, TypeError):
                pass
            except Exception:
                pass
                
            if self.uid_loading_dialog:
                self.uid_loading_dialog.close()
                self.uid_loading_dialog = None
                
            self._show_status(QCoreApplication.translate("MainWindow", "UID loaded successfully!"))
            
            # Update UI
            self._update_device_table_row(device, row)
            self._update_device_details(device)
            
            # Info popup removed as per request - only loading overlay was shown
            # if show_info:
            #    try:
            #        self._show_uid_info_dialog(device)
            #    except Exception:
            #        pass
        except Exception as e:
            logger.error(f"Error in _on_uid_load_success: {e}", exc_info=True)
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Warning"), 
                                f"UID loaded but UI update failed: {e}")

    def _on_uid_load_error(self, err):
        """Handle UID load error."""
        try:
            self.firmware_flasher.progress_update.disconnect(self._on_uid_progress)
        except (RuntimeError, TypeError):
            pass
        except Exception:
            pass
            
        if self.uid_loading_dialog:
            self.uid_loading_dialog.close()
            self.uid_loading_dialog = None
            
        QMessageBox.critical(self, QCoreApplication.translate("MainWindow", "Error"), f"{QCoreApplication.translate('MainWindow', 'Failed to load UID:')} {err}")


    def _adjust_layout_density(self, row_count: int):
        try:
            if row_count > 10:
                table_pt = max(8, self.TABLE_FONT_PT - 2)
                header_pt = max(9, self.HEADER_FONT_PT - 2)
                row_h = 30
                details_max = 260
            elif row_count > 4:
                table_pt = max(9, self.TABLE_FONT_PT - 1)
                header_pt = max(10, self.HEADER_FONT_PT - 1)
                row_h = 32
                details_max = 320
            else:
                table_pt = self.TABLE_FONT_PT
                header_pt = self.HEADER_FONT_PT
                row_h = 34
                details_max = 380
            tf = QFont()
            tf.setPointSize(table_pt)
            self.device_table.setFont(tf)
            hf = QFont()
            hf.setPointSize(header_pt)
            hf.setBold(True)
            try:
                self.device_table.horizontalHeader().setFont(hf)
            except Exception:
                pass
            try:
                self.device_table.verticalHeader().setDefaultSectionSize(row_h)
            except Exception:
                pass
            try:
                self.device_details_group.setMaximumHeight(details_max)
            except Exception:
                pass
        except Exception:
            pass
    
    def show_protected_config_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Admin Login"))
        v = QVBoxLayout()
        v.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Enter admin password")))
        pwd = QLineEdit()
        pwd.setEchoMode(QLineEdit.Password)
        v.addWidget(pwd)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v.addWidget(btns)
        dialog.setLayout(v)
        def on_accept():
            expected = self.config.get('admin_password', 'AWG')
            if pwd.text() == expected:
                dialog.accept()
            else:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Access Denied"), QCoreApplication.translate("MainWindow", "Wrong password"))
        btns.accepted.connect(on_accept)
        btns.rejected.connect(dialog.reject)
        if dialog.exec() == QDialog.Accepted:
            hub = QDialog(self)
            hub.setWindowTitle(QCoreApplication.translate("MainWindow", "Settings"))
            layout = QVBoxLayout()
            btn_email = QPushButton(QCoreApplication.translate("MainWindow", "Email Settings"))
            btn_email.clicked.connect(self.configure_email_dialog)
            layout.addWidget(btn_email)
            btn_onedrive = QPushButton(QCoreApplication.translate("MainWindow", "OneDrive Settings"))
            btn_onedrive.clicked.connect(self.configure_onedrive_dialog)
            layout.addWidget(btn_onedrive)
            btn_machine = QPushButton(QCoreApplication.translate("MainWindow", "Machine Types"))
            btn_machine.clicked.connect(self.configure_machine_types_dialog)
            layout.addWidget(btn_machine)
            btn_theme = QPushButton(QCoreApplication.translate("MainWindow", "Theme & Language"))
            btn_theme.clicked.connect(self.show_theme_language_dialog)
            layout.addWidget(btn_theme)
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(hub.reject)
            layout.addWidget(buttons)
            hub.setLayout(layout)
            hub.exec()
    
    def select_device(self, device: Device):
        """Handle device selection."""
        self.log(f"Selected device: {device.port} ({device.board_type.value})")
        self._show_status(f"Selected: {device.port}")

    def show_contact_support_dialog(self):
        """Open a dialog to send logs and error description to support."""
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Contact Support"))
        dialog.setMinimumWidth(600)

        v = QVBoxLayout()
        v.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Describe the issue you're experiencing:")))
        desc = QTextEdit()
        desc.setPlaceholderText(QCoreApplication.translate("MainWindow", "What happened? Steps to reproduce, expected vs actual behavior..."))
        v.addWidget(desc)

        include_logs_chk = QCheckBox(QCoreApplication.translate("MainWindow", "Include application logs"))
        include_logs_chk.setChecked(True)
        v.addWidget(include_logs_chk)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v.addWidget(btns)
        dialog.setLayout(v)

        def on_accept():
            if not check_internet_connection():
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Internet Required"), QCoreApplication.translate("MainWindow", "Please connect to the internet to send emails."))
                return

            description = desc.toPlainText().strip()
            if not description:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Missing Description"), QCoreApplication.translate("MainWindow", "Please provide a brief description of the issue."))
                return
            client_name = (self.client_name.text() if hasattr(self, 'client_name') else self.config.get('client_name', '')).strip()

            smtp_config = self.config.get('smtp', {})
            azure_config = self.config.get('azure', {})
            
            is_smtp_valid = smtp_config.get('host') and smtp_config.get('username')
            is_azure_valid = azure_config.get('enabled') and azure_config.get('client_id')
            
            if not is_smtp_valid and not is_azure_valid:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Email Not Configured"), QCoreApplication.translate("MainWindow", "Please configure Email settings first in Settings > Configure Email."))
                return

            # Check if logs are included, if not warn user
            if not include_logs_chk.isChecked():
                reply = QMessageBox.question(
                    dialog,
                    QCoreApplication.translate("MainWindow", "Include Logs?"),
                    QCoreApplication.translate("MainWindow", "Including application logs helps us analyze and resolve issues faster.\n\nDo you want to include logs?"),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    include_logs_chk.setChecked(True)

            # Prepare optional logs zip
            attachment_path = None
            try:
                if include_logs_chk.isChecked():
                    logs_dir = Config.LOGS_DIR
                    zip_path = Config.APPDATA_DIR / "logs_bundle.zip"
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        if logs_dir.exists():
                            for p in logs_dir.glob('*.log'):
                                zf.write(p, arcname=p.name)
                    attachment_path = zip_path if zip_path.exists() else None
            except Exception as e:
                logger.warning(f"Failed to build logs zip: {e}")
                attachment_path = None

            # Build email body
            operator_name = self.operator_name.text()
            
            # Gather info for template
            app_name = Config.APP_NAME
            app_version = get_version()[0]
            os_version = platform.platform()
            device_name = socket.gethostname()
            install_type = "Production" if getattr(sys, 'frozen', False) else "Development"
            timestamp = QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss')
            
            if include_logs_chk.isChecked():
                logs_status = QCoreApplication.translate("MainWindow", "Logs are attached to this email.")
            else:
                logs_status = ""

            body = QCoreApplication.translate("MainWindow", """Hello Support Team,

A new support request has been submitted from the {app_name} application.

User Description:
{user_description}

Application Information (Auto-collected):
App Version: {app_version}
Operating System: {os_version}
Device Name: {device_name}
Installation Type: {install_type}
Date & Time: {timestamp}

Logs Attachment:
{logs_status}

Please review the information above and contact the user if additional details are required.

Best regards,
{operator_name} Support System""").format(
                app_name=app_name,
                user_description=description,
                app_version=app_version,
                os_version=os_version,
                device_name=device_name,
                install_type=install_type,
                timestamp=timestamp,
                logs_status=logs_status,
                operator_name=operator_name
            )

            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            def update_progress(msg):
                self.log(msg)
                val = self.progress_bar.value()
                self.progress_bar.setValue(min(100, val + 20))

            success = False
            try:
                success = self.email_sender.send_email(
                    smtp_config=smtp_config,
                    recipients=["armida@kumuluswater.com"],
                    subject=f"AWG-Kumulus Support Request - {QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm')}",
                    body=body,
                    attachment_path=attachment_path,
                    progress_callback=update_progress,
                    azure_config=azure_config
                )
            except Exception as e:
                self.log(f"Error sending support email: {e}")
                QMessageBox.critical(dialog, QCoreApplication.translate("MainWindow", "Error"), f"{QCoreApplication.translate('MainWindow', 'Failed to send support email:')}\n{e}")
            finally:
                self.progress_bar.setVisible(False)

            if success:
                QMessageBox.information(dialog, QCoreApplication.translate("MainWindow", "Support Request Sent"), QCoreApplication.translate("MainWindow", "Your request has been sent to support. We'll get back to you soon."))
                dialog.accept()
            else:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Failed"), QCoreApplication.translate("MainWindow", "Could not send support request. Please check SMTP settings and try again."))

        btns.accepted.connect(on_accept)
        btns.rejected.connect(dialog.reject)
        dialog.exec()
    
    def on_machine_type_changed(self, text):
        """Handle machine type change."""
        # Disable flash firmware button when a machine type is selected
        if hasattr(self, 'flash_btn'):
            self.flash_btn.setEnabled(False)

        # Reset machine ID widgets to reflect the selected type
        machine_types = Config.get_machine_types(self.config)
        if text in machine_types:
            prefix = machine_types[text]['prefix']
            length = machine_types[text]['length']
            remaining = max(0, length - len(prefix))

            # Update prefix display
            self.machine_id_prefix_display.setText(prefix)

            # Configure suffix editor with numeric validator of exact length
            regex = QRegularExpression(fr"^\d{{{remaining}}}$")
            validator = QRegularExpressionValidator(regex)
            # Ensure the line edit exists for the editable combo box
            if self.machine_id_suffix.lineEdit():
                self.machine_id_suffix.lineEdit().setValidator(validator)
                self.machine_id_suffix.lineEdit().setPlaceholderText("0" * remaining)

            # Seed a few example suffixes for quick selection
            examples = [
                "0" * remaining,
                "1" * remaining,
                ("1234567890"[:remaining] if remaining > 0 else ""),
                "9" * remaining,
            ]
            self.machine_id_suffix.clear()
            # Filter empty or duplicates
            for ex in [e for e in examples if e]:
                if ex not in [self.machine_id_suffix.itemText(i) for i in range(self.machine_id_suffix.count())]:
                    self.machine_id_suffix.addItem(ex)

            # Update full ID placeholder and composed text
            placeholder = prefix + ("X" * remaining)
            self.machine_id.setPlaceholderText(f"e.g., {placeholder}")
            current_suffix = self.machine_id_suffix.currentText().strip()
            if current_suffix:
                self.machine_id.setText(prefix + current_suffix)
            else:
                self.machine_id.clear()

    def on_machine_id_suffix_changed(self, text):
        """Compose full machine ID from prefix + suffix as the user edits."""
        prefix = self.machine_id_prefix_display.text()
        suffix = text.strip()
        if prefix and suffix:
            self.machine_id.setText(prefix + suffix)
        else:
            self.machine_id.clear()
        # Persist to config
        try:
            self.config['machine_id_suffix'] = suffix
            self.config['machine_id'] = self.machine_id.text()
            Config.save_config(self.config)
        except Exception:
            pass
            
    def _save_client_name(self, text):
        """Save client name to config."""
        try:
            self.config['client_name'] = text.strip()
            Config.save_config(self.config)
        except Exception:
            pass
    
    def generate_report(self):
        """Generate Excel report."""
        try:
            # Validate inputs
            operator_name = self.operator_name.text()
            operator_email = self.operator_email.text()
            client_name = (self.client_name.text() if hasattr(self, 'client_name') else self.config.get('client_name', '')).strip()
            machine_id = self.machine_id.text()
            
            if not operator_name or not operator_email or not machine_id or not client_name:
                QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Validation Error"), 
                                  QCoreApplication.translate("MainWindow", "Please fill in Client Name, Operator Name, Operator Email, and Machine ID"))
                return
            
            # Validate machine ID format
            machine_type = self.machine_type.currentText()
            machine_types = Config.get_machine_types(self.config)
            type_config = machine_types[machine_type]
            
            is_valid, error_message = Config.validate_machine_id(machine_id, type_config)
            if not is_valid:
                QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Validation Error"), error_message)
                return
            
            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Generate report
            client_name = (self.client_name.text() if hasattr(self, 'client_name') else self.config.get('client_name', '')).strip()
            operator_info = {
                'name': operator_name,
                'email': operator_email,
                'client_name': client_name,
                'machine_type': machine_type,
                'machine_id': machine_id
            }
            
            report_path = self.report_generator.generate_report(
                self.devices, operator_info, machine_type, machine_id
            )
            
            self.last_report_path = report_path  # Store for email sending
            self.progress_bar.setValue(100)
            
            # Save to OneDrive if enabled
            if self.onedrive_manager.is_enabled():
                self.log(QCoreApplication.translate("MainWindow", "Syncing data to OneDrive..."))
                success = self.onedrive_manager.save_machine_data(
                    operator_name=operator_name,
                    operator_email=operator_email,
                    client_name=client_name,
                    machine_type=machine_type,
                    machine_id=machine_id,
                    devices=self.devices
                )
                if success:
                    self.log(QCoreApplication.translate("MainWindow", "[SUCCESS] Data synced to OneDrive successfully"))
                else:
                    self.log(QCoreApplication.translate("MainWindow", "[WARNING] OneDrive sync failed - check logs"))
            
            # Ask user to confirm data and send email
            reply = QMessageBox.question(
                self,
                QCoreApplication.translate("MainWindow", "Confirm Report & Send"),
                f"{QCoreApplication.translate('MainWindow', 'Report generated:')}\n{report_path}\n\n"
                f"{QCoreApplication.translate('MainWindow', 'Data Summary:')}\n"
                f"- {QCoreApplication.translate('MainWindow', 'Operator:')} {operator_name}\n"
                f"- {QCoreApplication.translate('MainWindow', 'Machine Type:')} {machine_type}\n"
                f"- {QCoreApplication.translate('MainWindow', 'Machine ID:')} {machine_id}\n"
                f"- {QCoreApplication.translate('MainWindow', 'Client Name:')} {client_name or '-'}\n"
                f"- {QCoreApplication.translate('MainWindow', 'Devices:')} {len(self.devices)}\n\n"
                f"{QCoreApplication.translate('MainWindow', 'Please check the report details above.')}\n\n"
                f"{QCoreApplication.translate('MainWindow', 'Click \'Yes\' to send this report via email now,')}\n"
                f"{QCoreApplication.translate('MainWindow', 'or \'No\' to save it locally without sending.')}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # User confirmed - send email automatically
                self.send_email_automatically()
            else:
                # User chose not to send
                QMessageBox.information(self, QCoreApplication.translate("MainWindow", "Report Saved"),
                                      QCoreApplication.translate("MainWindow", "Report saved locally."))
            
            # Update config
            self.save_operator_info()
            
        except Exception as e:
            self.log(f"Error generating report: {e}")
            QMessageBox.critical(self, QCoreApplication.translate("MainWindow", "Error"), f"{QCoreApplication.translate('MainWindow', 'Failed to generate report:')} {e}")
        finally:
            self.progress_bar.setVisible(False)

    def auto_generate_report_if_ready(self):
        """Silently generate an Excel report after refresh when inputs are valid.
        Skips confirmation and email sending.
        """
        try:
            operator_name = (self.operator_name.text() or "").strip()
            operator_email = (self.operator_email.text() or "").strip()
            client_name = (self.client_name.text() if hasattr(self, 'client_name') else self.config.get('client_name', '')).strip()
            machine_id = (self.machine_id.text() or "").strip()
            if not operator_name or not operator_email or not machine_id or not client_name:
                return  # Not ready; do nothing

            machine_type = self.machine_type.currentText()
            machine_types = Config.get_machine_types(self.config)
            type_config = machine_types.get(machine_type)
            if not type_config:
                return
            is_valid, error_message = Config.validate_machine_id(machine_id, type_config)
            if not is_valid:
                return

            client_name = (self.client_name.text() if hasattr(self, 'client_name') else self.config.get('client_name', '')).strip()
            operator_info = { 'name': operator_name, 'email': operator_email, 'client_name': client_name, 'machine_type': machine_type, 'machine_id': machine_id }
            report_path = self.report_generator.generate_report(
                self.devices, operator_info, machine_type, machine_id
            )
            self.last_report_path = report_path

            # Save to OneDrive if enabled
            if self.onedrive_manager.is_enabled():
                self.onedrive_manager.save_machine_data(
                    operator_name=operator_name,
                    operator_email=operator_email,
                    client_name=client_name,
                    machine_type=machine_type,
                    machine_id=machine_id,
                    devices=self.devices
                )
            # Minimal feedback in status bar
            self._show_status(QCoreApplication.translate("MainWindow", "Report generated automatically"))
        except Exception as e:
            logger.warning(f"Auto report generation skipped: {e}")
    
    def send_email(self):
        """Send email with report (manual trigger)."""
        # User requested that clicking "Send Email" triggers report generation and confirmation
        self.generate_report()
    
    def process_email_queue(self):
        """Process queued emails when internet is available."""
        # Check internet without blocking UI too much
        # (check_internet_connection uses a short timeout)
        if not check_internet_connection():
            return
            
        try:
            pending = self.email_sender.queue_manager.get_pending_emails()
            if not pending:
                return
                
            logger.info(f"Processing {len(pending)} queued emails...")
            
            for email_entry in pending:
                try:
                    # Extract ID
                    email_id = email_entry["id"]
                    
                    # Prepare attachment path
                    attachment_path = None
                    if email_entry.get("attachment_path"):
                        p = Path(email_entry["attachment_path"])
                        if p.exists():
                            attachment_path = p
                    
                    # Try to send
                    # Note: We pass queue_if_offline=False to avoid infinite queuing loop
                    # if the connection drops mid-process.
                    success = self.email_sender.send_email(
                        smtp_config=email_entry.get("smtp_config", {}),
                        recipients=email_entry.get("recipients", []),
                        subject=email_entry.get("subject", ""),
                        body=email_entry.get("body", ""),
                        attachment_path=attachment_path,
                        azure_config=email_entry.get("azure_config"),
                        sender_override=email_entry.get("sender_override"),
                        queue_if_offline=False
                    )
                    
                    if success:
                        self.email_sender.queue_manager.remove_from_queue(email_id)
                        logger.info(f"Successfully sent queued email {email_id}")
                    else:
                        logger.warning(f"Failed to send queued email {email_id}. Keeping in queue.")
                        
                except Exception as e:
                    logger.error(f"Error processing queued email {email_entry.get('id')}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in process_email_queue: {e}")

    def send_email_automatically(self):
        """Automatically send email with the last generated report."""
        if not check_internet_connection():
             QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Internet Required"), QCoreApplication.translate("MainWindow", "Please connect to the internet to send support emails."))
             return

        if not self.last_report_path or not self.last_report_path.exists():
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "No Report"), 
                              QCoreApplication.translate("MainWindow", "No report available to send."))
            return
        
        smtp_config = self.config.get('smtp', {})
        azure_config = self.config.get('azure', {})
        recipients = self.config.get('recipients', [])
        
        logger.info(f"Email Config Check: Azure Enabled={azure_config.get('enabled')}, SMTP Host={smtp_config.get('host')}")
        
        # Check configuration
        is_azure = azure_config.get('enabled', False)
        if not is_azure and not smtp_config.get('host'):
            reply = QMessageBox.question(
                self,
                QCoreApplication.translate("MainWindow", "Email Not Configured"),
                QCoreApplication.translate("MainWindow", "Email is not configured. Would you like to configure it now?"),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.configure_email_dialog()
            return
        
        if not recipients:
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "No Recipients"),
                              QCoreApplication.translate("MainWindow", "Please add email recipients in settings."))
            return
        
        if not is_azure and not smtp_config.get('username'):
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Email Not Configured"),
                              QCoreApplication.translate("MainWindow", "SMTP username not configured."))
            return
        
        try:
            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Update progress in log
            def update_progress(msg):
                self.log(msg)
                self.progress_bar.setValue(self.progress_bar.value() + 25)
            
            update_progress(QCoreApplication.translate("MainWindow", "Connecting to email server..."))
            
            # Get operator info for email body
            operator_name = self.operator_name.text()
            operator_email = self.operator_email.text()
            client_name = (self.client_name.text() if hasattr(self, 'client_name') else self.config.get('client_name', '')).strip()
            machine_type = self.machine_type.currentText()
            machine_id = self.machine_id.text()
            
            if not client_name:
                QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Validation Error"), QCoreApplication.translate("MainWindow", "Please fill in Client Name before sending email."))
                self.progress_bar.setVisible(False)
                return
            
            # Create detailed device summary for email
            device_summary = self._create_device_summary()
            
            client_name = (self.client_name.text() if hasattr(self, 'client_name') else self.config.get('client_name', '')).strip()
            
            email_body = QCoreApplication.translate("MainWindow", """AWG Kumulus Device Manager Report

Operator: {operator_name} ({operator_email})
Client Name: {client_name}
Machine Type: {machine_type}
Machine ID: {machine_id}
Devices Detected: {device_count}

DEVICE DETAILS:
{device_summary}

Please find the attached Excel report with complete device information including UIDs, hardware characteristics, and technical specifications.""").format(
                operator_name=operator_name,
                operator_email=operator_email,
                client_name=client_name or '-',
                machine_type=machine_type,
                machine_id=machine_id,
                device_count=len(self.devices),
                device_summary=device_summary
            )
            
            update_progress(QCoreApplication.translate("MainWindow", "Sending email..."))
            
            # Send email
            success = self.email_sender.send_email(
                smtp_config=smtp_config,
                recipients=recipients,
                subject=QCoreApplication.translate("MainWindow", "AWG Kumulus Report - {} - {} - {}").format(client_name or 'Client', machine_type, machine_id),
                body=email_body,
                attachment_path=self.last_report_path,
                progress_callback=update_progress,
                azure_config=azure_config,
                sender_override=operator_email if operator_email else None
            )
            
            self.progress_bar.setValue(100)
            
            if success:
                update_progress(QCoreApplication.translate("MainWindow", "Email sent successfully!"))
                QMessageBox.information(self, QCoreApplication.translate("MainWindow", "Email Sent"),
                                      QCoreApplication.translate("MainWindow", "Report sent successfully to:\n") +
                                      "\n".join(recipients))
            else:
                QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Email Failed"),
                                  QCoreApplication.translate("MainWindow", "Failed to send email. Check logs for details."))
            
        except Exception as e:
            self.log(f"Error sending email: {e}")
            QMessageBox.critical(self, QCoreApplication.translate("MainWindow", "Error"), 
                               f"{QCoreApplication.translate('MainWindow', 'Failed to send email:')}\n{str(e)}")
        finally:
            self.progress_bar.setVisible(False)
    
    def _create_device_summary(self) -> str:
        """Create a detailed summary of detected devices for email."""
        if not self.devices:
            return "No devices detected."
        
        summary_lines = []
        for i, device in enumerate(self.devices, 1):
            def _fmt_hex(val):
                try:
                    if val is None:
                        return None
                    if isinstance(val, int):
                        return f"0x{val:04X}"
                    s = str(val).strip()
                    if s.lower().startswith("0x"):
                        return f"0x{int(s,16):04X}"
                    return f"0x{int(s):04X}"
                except Exception:
                    return str(val)
            device_info = [
                f"Device {i}:",
                f"  Board Type: {device.board_type.value}",
                f"  Port: {device.port}",
                f"  UID: {device.uid or 'N/A'}",
                f"  Chip ID: {device.chip_id or 'N/A'}",
                f"  MAC Address: {device.mac_address or 'N/A'}",
                f"  Manufacturer: {device.manufacturer or 'N/A'}",
                f"  Serial Number: {device.serial_number or 'N/A'}",
                f"  Firmware Version: {device.firmware_version or 'N/A'}",
                f"  Hardware Version: {device.hardware_version or 'N/A'}",
                f"  Flash Size: {device.flash_size or 'N/A'}",
                f"  CPU Frequency: {device.cpu_frequency or 'N/A'}",
                f"  VID:PID: {_fmt_hex(device.vid)}:{_fmt_hex(device.pid)}" if device.vid and device.pid else "  VID:PID: N/A",
                ""
            ]
            summary_lines.extend(device_info)
        
        return "\n".join(summary_lines)
    
    def configure_email_dialog(self):
        """Open email configuration dialog with preset configurations and auto-detection."""
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Email Configuration"))
        dialog.setWindowState(Qt.WindowMaximized)
        
        main_layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        # Status banner
        self.onedrive_status_banner = QLabel(QCoreApplication.translate("MainWindow", "OneDrive is currently disabled"))
        self.onedrive_status_banner.setStyleSheet("background:#fff3cd;color:#664d03;padding:10px;border:1px solid #ffe69c;border-radius:6px;")
        layout.addWidget(self.onedrive_status_banner)
        
        # Email Provider Selection
        provider_group = QGroupBox(QCoreApplication.translate("MainWindow", "Email Provider"))
        provider_layout = QFormLayout()
        
        # Provider selection
        provider_combo = QComboBox()
        provider_combo.addItems(["Auto-detect from email", "Gmail", "Outlook/Hotmail", "Office 365", "Custom", "Azure (Graph API)"])
        provider_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Provider:")), provider_combo)
        
        # Select current provider
        if self.config.get('azure', {}).get('enabled'):
            provider_combo.setCurrentText('Azure (Graph API)')
        elif self.config.get('smtp', {}).get('host'):
             # Try to match SMTP host to provider
             host = self.config.get('smtp', {}).get('host')
             if 'gmail.com' in host:
                 provider_combo.setCurrentText('Gmail')
             elif 'outlook.com' in host or 'hotmail.com' in host:
                 provider_combo.setCurrentText('Outlook/Hotmail')
             elif 'office365.com' in host:
                 provider_combo.setCurrentText('Office 365')
             else:
                 provider_combo.setCurrentText('Custom')
        
        # Email Username (for auto-detection)
        smtp_user = QLineEdit()
        smtp_user.setText(self.config.get('smtp', {}).get('username', ''))
        smtp_user.setPlaceholderText("your.email@gmail.com")
        provider_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Email Address:")), smtp_user)
        
        # Azure Configuration Group (initially hidden unless Azure is selected)
        azure_group = QGroupBox(QCoreApplication.translate("MainWindow", "Azure Configuration"))
        azure_layout = QFormLayout()
        
        azure_client_id = QLineEdit()
        azure_client_id.setText(self.config.get('azure', {}).get('client_id', ''))
        azure_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Client ID:")), azure_client_id)
        
        azure_tenant_id = QLineEdit()
        azure_tenant_id.setText(self.config.get('azure', {}).get('tenant_id', ''))
        azure_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Tenant ID:")), azure_tenant_id)
        
        azure_client_secret = QLineEdit()
        azure_client_secret.setText(self.config.get('azure', {}).get('client_secret', ''))
        azure_client_secret.setEchoMode(QLineEdit.Password)
        azure_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Client Secret:")), azure_client_secret)
        
        azure_sender_email = QLineEdit()
        azure_sender_email.setText(self.config.get('azure', {}).get('sender_email', ''))
        azure_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Sender Email:")), azure_sender_email)
        
        azure_group.setLayout(azure_layout)
        # Add to main layout but keep reference to toggle visibility
        layout.addWidget(azure_group)
        
        # Auto-detect button
        auto_detect_btn = QPushButton(QCoreApplication.translate("MainWindow", "Auto-detect Settings"))
        auto_detect_btn.setMaximumWidth(180)
        provider_layout.addRow(QLabel(""), auto_detect_btn)
        
        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)
        
        # SMTP Configuration Group
        smtp_group = QGroupBox(QCoreApplication.translate("MainWindow", "SMTP Configuration"))
        smtp_layout = QFormLayout()
        
        # SMTP Server
        smtp_host = QLineEdit()
        smtp_host.setText(self.config.get('smtp', {}).get('host', ''))
        smtp_host.setPlaceholderText("e.g., smtp.gmail.com")
        smtp_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "SMTP Server:")), smtp_host)
        
        # Port
        smtp_port = QLineEdit()
        smtp_port.setText(str(self.config.get('smtp', {}).get('port', 587)))
        smtp_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Port:")), smtp_port)
        
        # TLS checkbox
        tls_checkbox = QCheckBox(QCoreApplication.translate("MainWindow", "Use TLS/STARTTLS"))
        tls_checkbox.setChecked(self.config.get('smtp', {}).get('tls', True))
        smtp_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Security:")), tls_checkbox)
        
        # Password
        smtp_pass = QLineEdit()
        smtp_pass.setEchoMode(QLineEdit.Password)
        smtp_layout.addRow(QLabel(QCoreApplication.translate("MainWindow", "Password:")), smtp_pass)
        
        smtp_group.setLayout(smtp_layout)
        layout.addWidget(smtp_group)
        
        # Recipients (Common for all providers)
        recipients_group = QGroupBox(QCoreApplication.translate("MainWindow", "Recipients"))
        recipients_layout = QVBoxLayout()
        recipients_text = QTextEdit()
        recipients_text.setMaximumHeight(100)
        recipients_text.setPlaceholderText(QCoreApplication.translate("MainWindow", "Enter email addresses, one per line"))
        recipients_text.setPlainText("\n".join(self.config.get('recipients', [])))
        recipients_layout.addWidget(recipients_text)
        recipients_group.setLayout(recipients_layout)
        layout.addWidget(recipients_group)
        
        # Dynamic Configuration Guide
        guide_group = QGroupBox(QCoreApplication.translate("MainWindow", "[GUIDE] Email Configuration Guide"))
        guide_layout = QVBoxLayout()
        
        # Dynamic guide label that changes based on provider selection
        self.dynamic_guide = QLabel(QCoreApplication.translate("MainWindow", "Select an email provider to see specific configuration instructions"))
        self.dynamic_guide.setOpenExternalLinks(True)
        self.dynamic_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0f8ff; padding: 8px; border-radius: 4px; border: 1px solid #b0d4f1;")
        guide_layout.addWidget(self.dynamic_guide)
        
        guide_group.setLayout(guide_layout)
        layout.addWidget(guide_group)
        
        # Test Button
        test_btn = QPushButton(QCoreApplication.translate("MainWindow", "Test Configuration"))
        test_btn.clicked.connect(lambda: test_configuration())
        layout.addWidget(test_btn)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        main_layout.addWidget(buttons)
        
        # Connect signals for auto-detection and preset configurations
        def test_configuration():
            """Test the current email configuration."""
            provider = provider_combo.currentText()
            
            # Handle Azure test
            if provider == 'Azure (Graph API)':
                # Construct config from UI fields to allow testing before saving
                azure_cfg = {
                    'enabled': True,
                    'client_id': azure_client_id.text().strip(),
                    'tenant_id': azure_tenant_id.text().strip(),
                    'client_secret': azure_client_secret.text().strip(),
                    'sender_email': azure_sender_email.text().strip()
                }
                
                recips_str = recipients_text.toPlainText().strip()
                recips = [r.strip() for r in recips_str.split('\n') if r.strip()]
                
                if not recips:
                     QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Missing Info"), QCoreApplication.translate("MainWindow", "Please add at least one recipient."))
                     return
                     
                if not azure_cfg['client_id'] or not azure_cfg['tenant_id'] or not azure_cfg['client_secret']:
                    QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Missing Info"), QCoreApplication.translate("MainWindow", "Please fill in all Azure configuration fields."))
                    return
                
                if not azure_cfg['sender_email']:
                    QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Missing Info"), QCoreApplication.translate("MainWindow", "Please enter a Sender Email."))
                    return
                
                # Show progress
                progress = QProgressDialog(QCoreApplication.translate("MainWindow", "Sending test email via Azure..."), None, 0, 0, dialog)
                progress.setWindowModality(Qt.WindowModal)
                progress.setMinimumDuration(0)
                progress.show()
                QApplication.processEvents()
                
                def cb(msg):
                    progress.setLabelText(msg)
                    QApplication.processEvents()
                
                # For testing, we use the sender email from the config field as the override
                # to ensure it works.
                test_sender = azure_cfg['sender_email']
                
                success = self.email_sender.send_email_azure(
                    azure_config=azure_cfg,
                    recipients=recips,
                    subject=QCoreApplication.translate("MainWindow", "Test Email from AWG Kumulus (Azure)"),
                    body=QCoreApplication.translate("MainWindow", "This is a test email to verify your Azure Graph API configuration."),
                    progress_callback=cb,
                    sender_override=test_sender
                )
                
                progress.close()
                if success:
                    QMessageBox.information(dialog, QCoreApplication.translate("MainWindow", "Success"), QCoreApplication.translate("MainWindow", "Test email sent successfully via Azure!"))
                else:
                    QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Failed"), 
                                      QCoreApplication.translate("MainWindow", "Failed to send test email.\n\n"
                                      "Note: Ensure 'Sender Email' is a valid user email address in your Azure tenant, "
                                      "not an application name."))
                return

            # Get current values
            host = smtp_host.text().strip()
            port_str = smtp_port.text().strip()
            user = smtp_user.text().strip()
            pwd = smtp_pass.text()
            recips_str = recipients_text.toPlainText().strip()
            recips = [r.strip() for r in recips_str.split('\n') if r.strip()]

            if not host or not port_str or not user:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Missing Info"), QCoreApplication.translate("MainWindow", "Please fill in Host, Port, and Email Address."))
                return
            
            if not recips:
                 QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Missing Info"), QCoreApplication.translate("MainWindow", "Please add at least one recipient."))
                 return

            try:
                port = int(port_str)
            except ValueError:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Invalid Port"), QCoreApplication.translate("MainWindow", "Port must be a number."))
                return

            cfg = {
                'host': host,
                'port': port,
                'username': user,
                'tls': tls_checkbox.isChecked()
            }

            # Show progress
            progress = QProgressDialog(QCoreApplication.translate("MainWindow", "Sending test email..."), None, 0, 0, dialog)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            def cb(msg):
                progress.setLabelText(msg)
                QApplication.processEvents()

            success = self.email_sender.send_email(
                smtp_config=cfg,
                recipients=recips,
                subject=QCoreApplication.translate("MainWindow", "Test Email from AWG Kumulus"),
                body=QCoreApplication.translate("MainWindow", "This is a test email to verify your SMTP configuration."),
                password=pwd if pwd else None, # Pass explicit password if provided
                progress_callback=cb
            )
            
            progress.close()
            
            if success:
                QMessageBox.information(dialog, QCoreApplication.translate("MainWindow", "Success"), QCoreApplication.translate("MainWindow", "Test email sent successfully!"))
            else:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Failed"), QCoreApplication.translate("MainWindow", "Failed to send test email. Check logs."))

        def auto_detect_settings():
            """Auto-detect SMTP settings based on email domain."""
            email = smtp_user.text().strip()
            if not email:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "No Email"), QCoreApplication.translate("MainWindow", "Please enter your email address first."))
                return
            
            # Extract domain
            if '@' not in email:
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Invalid Email"), QCoreApplication.translate("MainWindow", "Please enter a valid email address."))
                return
            
            domain = email.split('@')[1].lower()
            
            # Auto-detect settings based on domain
            if 'gmail.com' in domain:
                smtp_host.setText('smtp.gmail.com')
                smtp_port.setText('587')
                tls_checkbox.setChecked(True)
                provider_combo.setCurrentText('Gmail')
            elif 'outlook.com' in domain or 'hotmail.com' in domain:
                smtp_host.setText('smtp-mail.outlook.com')
                smtp_port.setText('587')
                tls_checkbox.setChecked(True)
                provider_combo.setCurrentText('Outlook/Hotmail')
            elif 'office365.com' in domain or 'microsoft.com' in domain:
                smtp_host.setText('smtp.office365.com')
                smtp_port.setText('587')
                tls_checkbox.setChecked(True)
                provider_combo.setCurrentText('Office 365')
            else:
                QMessageBox.information(dialog, QCoreApplication.translate("MainWindow", "Custom Domain"), 
                    QCoreApplication.translate("MainWindow", "Domain '{}' not recognized. Please configure manually or choose 'Custom'.").format(domain))
                provider_combo.setCurrentText('Custom')
            
            # Update the guide after auto-detection
            update_dynamic_guide()
        
        def apply_preset_config():
            """Apply preset configuration based on selected provider."""
            provider = provider_combo.currentText()
            
            # Toggle visibility of configuration groups
            is_azure = (provider == 'Azure (Graph API)')
            smtp_group.setVisible(not is_azure)
            azure_group.setVisible(is_azure)
            
            # Toggle visibility of auto-detect button and SMTP user field
            auto_detect_btn.setVisible(not is_azure)
            # smtp_user is needed for testing Azure override, so keep it visible but maybe rename label?
            # For now, let's keep it visible as it's used for SMTP username AND test override
            
            if provider == 'Gmail':
                smtp_host.setText('smtp.gmail.com')
                smtp_port.setText('587')
                tls_checkbox.setChecked(True)
            elif provider == 'Outlook/Hotmail':
                smtp_host.setText('smtp-mail.outlook.com')
                smtp_port.setText('587')
                tls_checkbox.setChecked(True)
            elif provider == 'Office 365':
                smtp_host.setText('smtp.office365.com')
                smtp_port.setText('587')
                tls_checkbox.setChecked(True)
            elif provider == 'Azure (Graph API)':
                # Disable SMTP fields or clear them, but keep them editable if user switches back
                pass
            elif provider == 'Custom':
                # Clear fields for custom configuration
                smtp_host.clear()
                smtp_port.setText('587')
                tls_checkbox.setChecked(True)
        
        # Initial visibility update
        apply_preset_config()
        
        # Function to update dynamic guide based on provider selection
        def update_dynamic_guide():
            """Update the dynamic guide based on selected provider."""
            provider = provider_combo.currentText()
            email = smtp_user.text().strip()
            
            if provider == "Auto-detect from email" and email:
                # Auto-detect based on email domain
                if '@' in email:
                    domain = email.split('@')[1].lower()
                    if 'gmail.com' in domain:
                        provider = 'Gmail'
                    elif 'outlook.com' in domain or 'hotmail.com' in domain:
                        provider = 'Outlook/Hotmail'
                    elif 'office365.com' in domain or 'microsoft.com' in domain:
                        provider = 'Office 365'
                    else:
                        provider = 'Custom'
            
            # Update guide based on provider
            if provider == 'Azure (Graph API)':
                guide_text = """
                <b>[EMAIL] Azure (Graph API) Configuration:</b><br>
                1. Uses Microsoft Graph API for sending emails.<br>
                2. Requires App Registration in Azure Portal.<br>
                3. Configuration is loaded from config file (client_id, client_secret, etc.).<br>
                <b>Note:</b> SMTP settings below are ignored when Azure is selected.<br>
                """
                self.dynamic_guide.setStyleSheet("color: #333; font-size: 10px; background: #e6f7ff; padding: 8px; border-radius: 4px; border: 1px solid #1890ff;")

            elif provider == 'Gmail':
                guide_text = """
                <b>[EMAIL] Gmail Configuration:</b><br>
                1. Enable 2-Step Verification: <a href="https://myaccount.google.com/security">https://myaccount.google.com/security</a><br>
                2. Generate App Password: <a href="https://myaccount.google.com/apppasswords">https://myaccount.google.com/apppasswords</a><br>
                3. Use App Password (16 characters) instead of your regular password<br>
                <b>Settings:</b> smtp.gmail.com, Port 587, TLS enabled<br><br>
                <b>[COMMON] Common Gmail Issues:</b><br>
                • <b>Error 535:</b> Wrong username/password - Use App Password<br>
                • <b>Error 534:</b> App Password required - Enable 2FA first<br>
                • <b>Still having issues?</b> <a href="https://support.google.com/mail/answer/7126229">Gmail Help</a>
                """
                self.dynamic_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0f8ff; padding: 8px; border-radius: 4px; border: 1px solid #b0d4f1;")
                
            elif provider == 'Outlook/Hotmail':
                guide_text = """
                <b>[EMAIL] Outlook/Hotmail Configuration:</b><br>
                1. Enable 2-Step Verification: <a href="https://account.microsoft.com/security">https://account.microsoft.com/security</a><br>
                2. Generate App Password: <a href="https://account.microsoft.com/security/app-passwords">https://account.microsoft.com/security/app-passwords</a><br>
                3. Use App Password instead of your regular password<br>
                <b>Settings:</b> smtp-mail.outlook.com, Port 587, TLS enabled<br><br>
                <b>[COMMON] Common Outlook Issues:</b><br>
                • <b>Error 535:</b> Wrong username/password - Use App Password<br>
                • <b>Error 534:</b> App Password required - Enable 2FA first<br>
                • <b>Still having issues?</b> <a href="https://support.microsoft.com/en-us/office/pop-imap-and-smtp-settings-for-outlook-8361e398-8af4-4e97-b147-6c6c4ac95353">Outlook Help</a>
                """
                self.dynamic_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff0f0; padding: 8px; border-radius: 4px; border: 1px solid #f1b0b0;")
                
            elif provider == 'Office 365':
                guide_text = """
                <b>[EMAIL] Office 365 Configuration:</b><br>
                1. Contact your IT administrator for SMTP settings<br>
                2. May require App Password: <a href="https://account.microsoft.com/security/app-passwords">https://account.microsoft.com/security/app-passwords</a><br>
                3. Some organizations disable SMTP authentication<br>
                <b>Settings:</b> smtp.office365.com, Port 587, TLS enabled<br><br>
                <b>[COMMON] Common Office 365 Issues:</b><br>
                • <b>Error 535:</b> Wrong username/password - Use App Password<br>
                • <b>Error 550:</b> Authentication failed - Check with IT admin<br>
                • <b>Still having issues?</b> Contact your IT administrator
                """
                self.dynamic_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0fff0; padding: 8px; border-radius: 4px; border: 1px solid #b0f1b0;")
                
            elif provider == 'Custom':
                guide_text = """
                <b>[EMAIL] Custom Email Configuration:</b><br>
                1. Contact your email provider for SMTP settings<br>
                2. Common settings: smtp.yourdomain.com, Port 587 or 465<br>
                3. Check if TLS/SSL is required<br>
                4. Verify username and password requirements<br><br>
                <b>[COMMON] Common Custom Issues:</b><br>
                • <b>Error 535:</b> Wrong username/password - Check credentials<br>
                • <b>Error 550:</b> Authentication failed - Check SMTP settings<br>
                • <b>Connection timeout:</b> Check firewall/antivirus settings<br>
                • <b>Still having issues?</b> Contact your email provider
                """
                self.dynamic_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff8f0; padding: 8px; border-radius: 4px; border: 1px solid #f1d0b0;")
                
            else:
                guide_text = """
                <b>[EMAIL] Email Configuration:</b><br>
                Select an email provider from the dropdown above to see specific configuration instructions.<br><br>
                <b>Supported Providers:</b><br>
                • <b>Gmail:</b> Personal Google accounts<br>
                • <b>Outlook/Hotmail:</b> Personal Microsoft accounts<br>
                • <b>Office 365:</b> Business Microsoft accounts<br>
                • <b>Custom:</b> Other email providers
                """
                self.dynamic_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0f8ff; padding: 8px; border-radius: 4px; border: 1px solid #b0d4f1;")
            
            self.dynamic_guide.setText(guide_text)
        
        # Connect signals
        auto_detect_btn.clicked.connect(auto_detect_settings)
        provider_combo.currentTextChanged.connect(apply_preset_config)
        provider_combo.currentTextChanged.connect(update_dynamic_guide)
        smtp_user.textChanged.connect(update_dynamic_guide)
        
        # Initial guide update
        update_dynamic_guide()
        
        # Save configuration logic definition
        def save_configuration():
            """Save the current email configuration."""
            provider = provider_combo.currentText()
            logger.info(f"Saving configuration for provider: '{provider}'")
            
            recips_str = recipients_text.toPlainText().strip()
            recips = [r.strip() for r in recips_str.split('\n') if r.strip()]
            
            # Common config
            self.config['recipients'] = recips
            
            # Ensure azure section exists
            if 'azure' not in self.config:
                 self.config['azure'] = {}
            
            if provider == 'Azure (Graph API)':
                # Save Azure config
                self.config['azure'].update({
                    'enabled': True,
                    'client_id': azure_client_id.text().strip(),
                    'tenant_id': azure_tenant_id.text().strip(),
                    'client_secret': azure_client_secret.text().strip(),
                    'sender_email': azure_sender_email.text().strip()
                })
            else:
                # Disable Azure
                self.config['azure']['enabled'] = False
                
                # Save SMTP details
                try:
                    port = int(smtp_port.text().strip())
                except ValueError:
                    port = 587
                    
                self.config['smtp'] = {
                    'host': smtp_host.text().strip(),
                    'port': port,
                    'username': smtp_user.text().strip(),
                    'tls': tls_checkbox.isChecked()
                }
                
                # Save password securely if provided
                pwd = smtp_pass.text()
                if pwd:
                    self.email_sender.save_credentials(smtp_user.text(), pwd)
            
            Config.save_config(self.config)
            QMessageBox.information(self, "Configuration Saved", "Email configuration saved successfully!")
            dialog.accept()
            
        # Override the dialog buttons to use our custom save logic
        buttons.accepted.disconnect() # Disconnect default accept
        buttons.accepted.connect(save_configuration)
        
        dialog.exec()
    
    def flash_firmware_dialog(self):
        """Open firmware flashing dialog."""
        # Allow opening without devices for tour/testing purposes, but show warning
        if not self.devices:
             # Just a non-blocking notification or empty state in dialog
             pass
        
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Flash Firmware"))
        dialog.setMinimumWidth(500)
        dialog.setObjectName("flash_firmware_dialog")
        # Remove Maximize call to keep dialog compact
        # dialog.setWindowState(Qt.WindowMaximized)
        
        main_layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        # Device Selection
        device_group = QGroupBox(QCoreApplication.translate("MainWindow", "Select Device"))
        device_layout = QVBoxLayout()
        
        device_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Choose device to flash:")))
        device_list = QListWidget()
        device_list.setObjectName("flash_device_list")
        device_list.setMaximumHeight(70)  # Limit height to make it smaller
        
        if self.devices:
            for device in self.devices:
                item_text = f"{device.board_type.value} - {device.port}"
                if device.manufacturer:
                    item_text += f" ({device.manufacturer})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, device)
                device_list.addItem(item)
            device_list.setCurrentRow(0)  # Select first device
        else:
            # Add a placeholder item if no devices
            item = QListWidgetItem(QCoreApplication.translate("MainWindow", "No devices detected"))
            item.setFlags(Qt.NoItemFlags) # Disable selection
            device_list.addItem(item)
            
        device_layout.addWidget(device_list)
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)
        
        # Firmware Source Selection
        firmware_group = QGroupBox(QCoreApplication.translate("MainWindow", "Firmware Source"))
        firmware_layout = QVBoxLayout()
        
        # Source type selection
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Source Type:")))
        source_combo = QComboBox()
        source_combo.setObjectName("flash_source_combo")
        source_combo.addItems([
            QCoreApplication.translate("MainWindow", "Local File (.bin/.elf)"),
            QCoreApplication.translate("MainWindow", "URL Download"),
            QCoreApplication.translate("MainWindow", "GitLab Repository")
        ])
        source_layout.addWidget(source_combo)
        firmware_layout.addLayout(source_layout)
        
        # File selection
        file_layout = QHBoxLayout()
        file_path = QLineEdit()
        file_path.setObjectName("flash_file_path")
        file_path.setPlaceholderText(QCoreApplication.translate("MainWindow", "Select firmware file or enter URL..."))
        file_layout.addWidget(file_path)
        
        browse_btn = QPushButton(QCoreApplication.translate("MainWindow", "Browse"))
        browse_btn.setObjectName("flash_browse_btn")
        browse_btn.clicked.connect(lambda: self._browse_firmware_file(file_path))
        file_layout.addWidget(browse_btn)
        firmware_layout.addLayout(file_layout)
        
        # Firmware Configuration Guide
        # Toggle Button
        toggle_guide_btn = QPushButton("Show Firmware Flashing Guide ➤")
        toggle_guide_btn.setCheckable(True)
        toggle_guide_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                font-weight: bold;
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-radius: 3px;
            }
        """)
        layout.addWidget(toggle_guide_btn)

        firmware_guide_group = QGroupBox("Firmware Flashing Guide")
        firmware_guide_layout = QVBoxLayout()
        
        # Supported Formats Guide
        formats_guide = QLabel("""
        <b>[FORMATS] Supported Firmware Formats:</b><br>
        • <b>.bin files:</b> Binary firmware files (most common)<br>
        • <b>.elf files:</b> Executable and Linkable Format files<br>
        • <b>URL downloads:</b> Direct download from web URLs<br>
        • <b>GitLab repositories:</b> Download from GitLab CI/CD artifacts
        """)
        formats_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0f8ff; padding: 8px; border-radius: 4px; border: 1px solid #b0d4f1;")
        firmware_guide_layout.addWidget(formats_guide)
        
        # Board-Specific Guide
        board_guide = QLabel(QCoreApplication.translate("MainWindow", """
        <b>[BOARD] Board-Specific Requirements:</b><br>
        • <b>STM32:</b> Requires STM32CubeProgrammer or OpenOCD<br>
        • <b>Arduino:</b> Uses avrdude for AVR-based boards<br>
        • <b>Generic:</b> Basic serial communication support
        """))
        board_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff0f0; padding: 8px; border-radius: 4px; border: 1px solid #f1b0b0;")
        firmware_guide_layout.addWidget(board_guide)
        
        # Troubleshooting Guide
        firmware_troubleshooting_guide = QLabel(QCoreApplication.translate("MainWindow", """
        <b>[TROUBLESHOOTING] Firmware Flashing Troubleshooting:</b><br>
        • <b>Device not found:</b> Check USB connection and drivers<br>
        • <b>Permission denied:</b> Run as administrator (Windows) or use sudo (Linux)<br>
        • <b>Flash failed:</b> Put device in bootloader mode manually<br>
        • <b>Wrong file format:</b> Ensure file matches board type<br>
        • <b>Still having issues?</b> Check: <a href="https://www.st.com/en/development-tools/stm32cubeprog.html">STM32 Docs</a>
        """))
        firmware_troubleshooting_guide.setOpenExternalLinks(True)
        firmware_troubleshooting_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff8f0; padding: 8px; border-radius: 4px; border: 1px solid #f1d0b0;")
        firmware_guide_layout.addWidget(firmware_troubleshooting_guide)
        
        firmware_guide_group.setLayout(firmware_guide_layout)
        firmware_guide_group.setVisible(False)  # Initially hidden
        layout.addWidget(firmware_guide_group)

        # Connect toggle button
        def on_guide_toggle(checked):
            firmware_guide_group.setVisible(checked)
            toggle_guide_btn.setText("Hide Firmware Flashing Guide ▼" if checked else "Show Firmware Flashing Guide ➤")
            
        toggle_guide_btn.clicked.connect(on_guide_toggle)
        
        firmware_group.setLayout(firmware_layout)
        layout.addWidget(firmware_group)
        
        # Flash Options
        options_group = QGroupBox("Flash Options")
        options_layout = QVBoxLayout()
        
        # Erase flash before flashing
        erase_checkbox = QCheckBox("Erase flash before flashing")
        erase_checkbox.setChecked(True)
        options_layout.addWidget(erase_checkbox)
        
        # Verify after flashing
        verify_checkbox = QCheckBox("Verify flash after completion")
        verify_checkbox.setChecked(True)
        options_layout.addWidget(verify_checkbox)
        
        # Boot mode selection
        boot_layout = QHBoxLayout()
        boot_layout.addWidget(QLabel("Boot Mode:"))
        boot_combo = QComboBox()
        boot_combo.addItems(["Normal Boot", "Bootloader Mode", "Auto-detect"])
        boot_combo.setCurrentText("Auto-detect")
        boot_layout.addWidget(boot_combo)
        options_layout.addLayout(boot_layout)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Progress and status
        progress_group = QGroupBox("Status")
        progress_layout = QVBoxLayout()
        
        self.flash_progress = QProgressBar()
        self.flash_progress.setVisible(False)
        progress_layout.addWidget(self.flash_progress)
        
        self.flash_status = QLabel("Ready to flash firmware")
        self.flash_status.setStyleSheet("color: #666;")
        progress_layout.addWidget(self.flash_status)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        flash_btn = buttons.button(QDialogButtonBox.Ok)
        flash_btn.setText("Flash Firmware")
        
        # Disable flash button if no devices
        if not self.devices:
            flash_btn.setEnabled(False)
            
        flash_btn.clicked.connect(lambda: self._start_flashing(
            dialog, 
            device_list.currentItem().data(Qt.UserRole) if device_list.currentItem() and device_list.currentItem().data(Qt.UserRole) else None,
            file_path.text(), erase_checkbox.isChecked(),
            verify_checkbox.isChecked(), boot_combo.currentText()
        ))
        buttons.rejected.connect(dialog.reject)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        main_layout.addWidget(buttons)
        
        if dialog.exec():
            pass  # Dialog was accepted
    def read_uid_dialog(self):
        """Flash GetMachineUid.bin and read the UID from the device."""
        # Get list of devices currently shown in table
        devices = getattr(self, 'filtered_devices', self.devices)
        device = None
        row = -1
        
        # 1. Check for checked items (checkbox in column 0)
        for r in range(self.device_table.rowCount()):
            item = self.device_table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                if 0 <= r < len(devices):
                    device = devices[r]
                    row = r
                    break
        
        # 2. If no checkbox checked, check for selected row
        if not device:
            selected_items = self.device_table.selectedItems()
            if selected_items:
                row = selected_items[0].row()
                if 0 <= row < len(devices):
                    device = devices[row]
        
        if not device:
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "No Device"),
                                QCoreApplication.translate("MainWindow", "Please check or select a board from the table first."))
            return

        self._load_device_uid(device, row, show_info=True)

    def _browse_firmware_file(self, file_path_widget):
        """Browse for firmware file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("MainWindow", "Select Firmware File"),
            "",
            QCoreApplication.translate("MainWindow", "Firmware Files (*.bin *.elf);;Binary Files (*.bin);;ELF Files (*.elf);;All Files (*)")
        )
        if file_path:
            file_path_widget.setText(file_path)
    
    def _create_source_inputs(self):
        """Create source input widgets for firmware dialog."""
        self.source_inputs = {}
        
        # Local file input
        local_layout = QVBoxLayout()
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "File Path:")))
        firmware_path = QLineEdit()
        firmware_path.setPlaceholderText(QCoreApplication.translate("MainWindow", "Enter file path..."))
        file_layout.addWidget(firmware_path)
        
        browse_btn = QPushButton(QCoreApplication.translate("MainWindow", "Browse"))
        browse_btn.clicked.connect(lambda: self._browse_firmware_file(firmware_path))
        file_layout.addWidget(browse_btn)
        local_layout.addLayout(file_layout)
        self.source_inputs["Local File"] = local_layout
        
        # GitHub input
        github_layout = QVBoxLayout()
        github_repo_layout = QHBoxLayout()
        github_repo_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Repository (owner/repo):")))
        github_repo = QLineEdit()
        github_repo.setPlaceholderText(QCoreApplication.translate("MainWindow", "e.g., espressif/arduino-esp32"))
        github_repo_layout.addWidget(github_repo)
        github_layout.addLayout(github_repo_layout)
        
        github_release_layout = QHBoxLayout()
        github_release_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Release Tag (optional):")))
        github_release = QLineEdit()
        github_release.setPlaceholderText(QCoreApplication.translate("MainWindow", "Leave empty for latest"))
        github_release_layout.addWidget(github_release)
        github_layout.addLayout(github_release_layout)
        
        github_asset_layout = QHBoxLayout()
        github_asset_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Asset Name (optional):")))
        github_asset = QLineEdit()
        github_asset.setPlaceholderText(QCoreApplication.translate("MainWindow", "Leave empty for auto-detect"))
        github_asset_layout.addWidget(github_asset)
        github_layout.addLayout(github_asset_layout)
        
        self.source_inputs["GitHub Release"] = github_layout
        
        # GitLab input
        gitlab_layout = QVBoxLayout()
        gitlab_project_layout = QHBoxLayout()
        gitlab_project_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Project ID:")))
        gitlab_project = QLineEdit()
        gitlab_project.setPlaceholderText(QCoreApplication.translate("MainWindow", "e.g., 12345"))
        gitlab_project_layout.addWidget(gitlab_project)
        gitlab_layout.addLayout(gitlab_project_layout)
        
        gitlab_pipeline_layout = QHBoxLayout()
        gitlab_pipeline_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Pipeline ID (optional):")))
        gitlab_pipeline = QLineEdit()
        gitlab_pipeline.setPlaceholderText(QCoreApplication.translate("MainWindow", "Leave empty for latest"))
        gitlab_pipeline_layout.addWidget(gitlab_pipeline)
        gitlab_layout.addLayout(gitlab_pipeline_layout)
        
        gitlab_artifact_layout = QHBoxLayout()
        gitlab_artifact_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Artifact Name (optional):")))
        gitlab_artifact = QLineEdit()
        gitlab_artifact.setPlaceholderText(QCoreApplication.translate("MainWindow", "Leave empty for auto-detect"))
        gitlab_artifact_layout.addWidget(gitlab_artifact)
        gitlab_layout.addLayout(gitlab_artifact_layout)
        
        self.source_inputs["GitLab Pipeline"] = gitlab_layout
        
        # URL input
        url_layout = QVBoxLayout()
        url_input_layout = QHBoxLayout()
        url_input_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "URL:")))
        firmware_url = QLineEdit()
        firmware_url.setPlaceholderText(QCoreApplication.translate("MainWindow", "https://example.com/firmware.bin"))
        url_input_layout.addWidget(firmware_url)
        url_layout.addLayout(url_input_layout)
        
        url_name_layout = QHBoxLayout()
        url_name_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Name:")))
        firmware_name = QLineEdit()
        firmware_name.setPlaceholderText(QCoreApplication.translate("MainWindow", "Firmware Name"))
        url_name_layout.addWidget(firmware_name)
        url_layout.addLayout(url_name_layout)
        
        url_version_layout = QHBoxLayout()
        url_version_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Version:")))
        firmware_version = QLineEdit()
        firmware_version.setPlaceholderText("1.0.0")
        url_version_layout.addWidget(firmware_version)
        url_layout.addLayout(url_version_layout)
        
        self.source_inputs["URL Download"] = url_layout
        
        # Database input
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Select Firmware:")))
        firmware_combo = QComboBox()
        db_layout.addWidget(firmware_combo)
        self.source_inputs["Firmware Database"] = db_layout
    
    def _start_enhanced_flashing(self, dialog, device_list, source_combo, erase_checkbox, 
                                verify_checkbox, backup_checkbox, progress_bar, status_label):
        """Start enhanced firmware flashing process."""
        current_item = device_list.currentItem()
        if not current_item:
            QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "No Device"), 
                              QCoreApplication.translate("MainWindow", "Please select a device"))
            return
        
        device = current_item.data(Qt.UserRole)
        source_type = source_combo.currentText()
        
        # Get source-specific inputs
        source_widget = self.source_container_layout.itemAt(0).widget()
        source_layout = source_widget.layout()
        
        try:
            if source_type == "Local File":
                file_path_widget = source_layout.itemAt(0).layout().itemAt(1).widget()
                firmware_source = file_path_widget.text().strip()
                
                if not firmware_source:
                    QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "No File"), 
                                      QCoreApplication.translate("MainWindow", "Please select a firmware file"))
                    return
                
                # Flash local file
                self._flash_local_file(device, firmware_source, erase_checkbox.isChecked(),
                                     verify_checkbox.isChecked(), backup_checkbox.isChecked(),
                                     progress_bar, status_label)
                
            elif source_type == "GitHub Release":
                repo_widget = source_layout.itemAt(0).layout().itemAt(1).widget()
                release_widget = source_layout.itemAt(1).layout().itemAt(1).widget()
                asset_widget = source_layout.itemAt(2).layout().itemAt(1).widget()
                
                repo = repo_widget.text().strip()
                release_tag = release_widget.text().strip() or None
                asset_name = asset_widget.text().strip() or None
                
                if not repo:
                    QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "No Repository"), 
                                      QCoreApplication.translate("MainWindow", "Please enter GitHub repository"))
                    return
                
                # Flash from GitHub
                self._flash_from_github(device, repo, release_tag, asset_name,
                                     erase_checkbox.isChecked(), verify_checkbox.isChecked(),
                                     backup_checkbox.isChecked(), progress_bar, status_label)
                
            elif source_type == "GitLab Pipeline":
                project_widget = source_layout.itemAt(0).layout().itemAt(1).widget()
                pipeline_widget = source_layout.itemAt(1).layout().itemAt(1).widget()
                artifact_widget = source_layout.itemAt(2).layout().itemAt(1).widget()
                
                project_id = project_widget.text().strip()
                pipeline_id = pipeline_widget.text().strip() or None
                artifact_name = artifact_widget.text().strip() or None
                
                if not project_id:
                    QMessageBox.warning(dialog, "No Project", "Please enter GitLab project ID")
                    return
                
                # Flash from GitLab
                self._flash_from_gitlab(device, project_id, pipeline_id, artifact_name,
                                      erase_checkbox.isChecked(), verify_checkbox.isChecked(),
                                      backup_checkbox.isChecked(), progress_bar, status_label)
                
            elif source_type == "URL Download":
                url_widget = source_layout.itemAt(0).layout().itemAt(1).widget()
                name_widget = source_layout.itemAt(1).layout().itemAt(1).widget()
                version_widget = source_layout.itemAt(2).layout().itemAt(1).widget()
                
                url = url_widget.text().strip()
                name = name_widget.text().strip()
                version = version_widget.text().strip()
                
                if not url or not name or not version:
                    QMessageBox.warning(dialog, "Incomplete Info", "Please fill all URL fields")
                    return
                
                # Flash from URL
                self._flash_from_url(device, url, name, version,
                                   erase_checkbox.isChecked(), verify_checkbox.isChecked(),
                                   backup_checkbox.isChecked(), progress_bar, status_label)
                
            elif source_type == "Firmware Database":
                firmware_combo = source_layout.itemAt(1).widget()
                firmware_id = firmware_combo.currentData()
                
                if not firmware_id:
                    QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "No Firmware"), 
                                      QCoreApplication.translate("MainWindow", "Please select firmware from database"))
                    return
                
                # Flash from database
                self._flash_from_database(device, firmware_id,
                                        erase_checkbox.isChecked(), verify_checkbox.isChecked(),
                                        backup_checkbox.isChecked(), progress_bar, status_label)
        
        except Exception as e:
            status_label.setText(QCoreApplication.translate("MainWindow", "Error: {}").format(str(e)))
            status_label.setStyleSheet("color: red;")
            logger.error(f"Enhanced flashing error: {e}")
    
    def _flash_local_file(self, device, file_path, erase_flash, verify_flash, backup_flash, 
                         progress_bar, status_label):
        """Flash firmware from local file."""
        def progress_callback(message):
            status_label.setText(message)
            QApplication.processEvents()
        
        try:
            progress_bar.setValue(10)
            progress_callback("Starting local file flash...")
            
            # Backup if requested
            if backup_flash:
                progress_callback("Backing up current firmware...")
                self.firmware_flasher.firmware_manager.backup_device_firmware(device, "manual_backup")
                progress_bar.setValue(30)
            
            # Flash firmware
            progress_callback("Flashing firmware...")
            success = self.firmware_flasher.flash_firmware(device, file_path, progress_callback)
            
            if success:
                progress_bar.setValue(100)
                status_label.setText("[SUCCESS] Firmware flashed successfully!")
                status_label.setStyleSheet("color: green;")
                
                # Save to OneDrive if enabled
                if self.onedrive_manager.is_enabled():
                    firmware_info = {
                        "name": Path(file_path).name,
                        "version": "local_file",
                        "source": "local_file",
                        "file_path": file_path
                    }
                    self.onedrive_manager.save_firmware_file(
                        self.config.get('operator', {}).get('name', 'Unknown'),
                        self.machine_type.currentText(),
                        self.machine_id.text(),
                        Path(file_path),
                        firmware_info
                    )
            else:
                status_label.setText(QCoreApplication.translate("MainWindow", "[ERROR] Firmware flashing failed!"))
                status_label.setStyleSheet("color: red;")
        
        except Exception as e:
            status_label.setText(QCoreApplication.translate("MainWindow", "[ERROR] Error: {}").format(str(e)))
            status_label.setStyleSheet("color: red;")
            logger.error(f"Local file flashing error: {e}")
    
    def _flash_from_github(self, device, repo, release_tag, asset_name, erase_flash, 
                          verify_flash, backup_flash, progress_bar, status_label):
        """Flash firmware from GitHub release."""
        def progress_callback(message):
            status_label.setText(message)
            QApplication.processEvents()
        
        try:
            progress_bar.setValue(10)
            progress_callback("Connecting to GitHub...")
            
            # Flash from GitHub
            success = self.firmware_flasher.flash_from_github(
                device, repo, release_tag, asset_name, progress_callback
            )
            
            if success:
                progress_bar.setValue(100)
                status_label.setText("[SUCCESS] GitHub firmware flashed successfully!")
                status_label.setStyleSheet("color: green;")
            else:
                status_label.setText("[ERROR] GitHub firmware flashing failed!")
                status_label.setStyleSheet("color: red;")
        
        except Exception as e:
            status_label.setText(f"[ERROR] Error: {str(e)}")
            status_label.setStyleSheet("color: red;")
            logger.error(f"GitHub flashing error: {e}")
    
    def _flash_from_gitlab(self, device, project_id, pipeline_id, artifact_name, 
                          erase_flash, verify_flash, backup_flash, progress_bar, status_label):
        """Flash firmware from GitLab pipeline."""
        def progress_callback(message):
            status_label.setText(message)
            QApplication.processEvents()
        
        try:
            progress_bar.setValue(10)
            progress_callback(QCoreApplication.translate("MainWindow", "Connecting to GitLab..."))
            
            # Flash from GitLab
            success = self.firmware_flasher.flash_from_gitlab(
                device, project_id, pipeline_id, artifact_name, progress_callback
            )
            
            if success:
                progress_bar.setValue(100)
                status_label.setText(QCoreApplication.translate("MainWindow", "[SUCCESS] GitLab firmware flashed successfully!"))
                status_label.setStyleSheet("color: green;")
            else:
                status_label.setText(QCoreApplication.translate("MainWindow", "[ERROR] GitLab firmware flashing failed!"))
                status_label.setStyleSheet("color: red;")
        
        except Exception as e:
            status_label.setText(QCoreApplication.translate("MainWindow", "[ERROR] Error: {}").format(str(e)))
            status_label.setStyleSheet("color: red;")
            logger.error(f"GitLab flashing error: {e}")
    
    def _flash_from_url(self, device, url, name, version, erase_flash, verify_flash, 
                       backup_flash, progress_bar, status_label):
        """Flash firmware from URL."""
        def progress_callback(message):
            status_label.setText(message)
            QApplication.processEvents()
        
        try:
            progress_bar.setValue(10)
            progress_callback("Downloading from URL...")
            
            # Flash from URL
            success = self.firmware_flasher.flash_from_url(
                device, url, name, version, progress_callback
            )
            
            if success:
                progress_bar.setValue(100)
                status_label.setText("[SUCCESS] URL firmware flashed successfully!")
                status_label.setStyleSheet("color: green;")
            else:
                status_label.setText("[ERROR] URL firmware flashing failed!")
                status_label.setStyleSheet("color: red;")
        
        except Exception as e:
            status_label.setText(f"[ERROR] Error: {str(e)}")
            status_label.setStyleSheet("color: red;")
            logger.error(f"URL flashing error: {e}")
    
    def _flash_from_database(self, device, firmware_id, erase_flash, verify_flash, 
                           backup_flash, progress_bar, status_label):
        """Flash firmware from database."""
        def progress_callback(message):
            status_label.setText(message)
            QApplication.processEvents()
        
        try:
            progress_bar.setValue(10)
            progress_callback(QCoreApplication.translate("MainWindow", "Loading firmware from database..."))
            
            # Flash from database
            success = self.firmware_flasher.flash_firmware_by_id(
                device, firmware_id, progress_callback
            )
            
            if success:
                progress_bar.setValue(100)
                status_label.setText(QCoreApplication.translate("MainWindow", "[SUCCESS] Database firmware flashed successfully!"))
                status_label.setStyleSheet("color: green;")
            else:
                status_label.setText(QCoreApplication.translate("MainWindow", "[ERROR] Database firmware flashing failed!"))
                status_label.setStyleSheet("color: red;")
        
        except Exception as e:
            status_label.setText(QCoreApplication.translate("MainWindow", "[ERROR] Error: {}").format(str(e)))
            status_label.setStyleSheet("color: red;")
            logger.error(f"Database flashing error: {e}")
    
    def _update_firmware_status(self, device_list):
        """Update firmware status for selected device."""
        current_item = device_list.currentItem()
        if not current_item:
            return
        
        device = current_item.data(Qt.UserRole)
        
        try:
            # Get firmware status
            status_info = self.firmware_flasher.get_device_firmware_status(device)
            
            # Update status label
            status_text = f"""
            <b>Device: {device.get_display_name()}</b><br>
            <b>Current Version:</b> {status_info['current_version']}<br>
            <b>Status:</b> {status_info['status']}<br>
            <b>Available Updates:</b> {status_info['available_updates']}<br>
            <b>Latest Version:</b> {status_info['latest_version']}<br>
            <b>Backups:</b> {status_info['backups_count']}<br>
            <b>Last Backup:</b> {status_info['last_backup'] or 'Never'}
            """
            
            if hasattr(self, 'firmware_status_label'):
                self.firmware_status_label.setText(status_text)
            
            # Update updates list
            if hasattr(self, 'updates_list'):
                self.updates_list.clear()
                for update in status_info['updates']:
                    item_text = f"{update['name']} v{update['version']} - {update['source']}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, update)
                    self.updates_list.addItem(item)
            
            # Update backups list
            if hasattr(self, 'backups_list'):
                self.backups_list.clear()
                for backup in status_info['backups']:
                    item_text = f"Backup {backup['backup_date'][:10]} - {backup['firmware_info']['version']}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, backup)
                    self.backups_list.addItem(item)
        
        except Exception as e:
            logger.error(f"Failed to update firmware status: {e}")
    
    def _rollback_firmware(self, device_list):
        """Rollback firmware to selected backup."""
        current_item = device_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "No Device"), 
                              QCoreApplication.translate("MainWindow", "Please select a device"))
            return
        
        device = current_item.data(Qt.UserRole)
        
        if not hasattr(self, 'backups_list'):
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "No Backups"), 
                              QCoreApplication.translate("MainWindow", "No backups list available"))
            return
        
        backup_item = self.backups_list.currentItem()
        if not backup_item:
            QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "No Backup"), 
                              QCoreApplication.translate("MainWindow", "Please select a backup to rollback to"))
            return
        
        backup_data = backup_item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, QCoreApplication.translate("MainWindow", "Confirm Rollback"),
            QCoreApplication.translate("MainWindow", "Are you sure you want to rollback to {}?").format(backup_data['firmware_info']['version']),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Find backup index
                backups = self.firmware_flasher.firmware_manager.get_device_backups(device)
                backup_index = 0
                for i, backup in enumerate(backups):
                    if backup.backup_date == backup_data['backup_date']:
                        backup_index = i
                        break
                
                def progress_callback(message):
                    self.log(message)
                
                success = self.firmware_flasher.rollback_firmware(device, backup_index, progress_callback)
                
                if success:
                    QMessageBox.information(self, QCoreApplication.translate("MainWindow", "Success"), 
                                          QCoreApplication.translate("MainWindow", "Firmware rollback completed successfully!"))
                    self._update_firmware_status(device_list)
                else:
                    QMessageBox.warning(self, QCoreApplication.translate("MainWindow", "Failed"), 
                                      QCoreApplication.translate("MainWindow", "Firmware rollback failed!"))
            
            except Exception as e:
                QMessageBox.critical(self, QCoreApplication.translate("MainWindow", "Error"), 
                                   QCoreApplication.translate("MainWindow", "Rollback error: {}").format(str(e)))
                logger.error(f"Rollback error: {e}")
    
    def _start_flashing(self, dialog, device, firmware_source, erase_flash, verify_flash, boot_mode):
        """Start the firmware flashing process."""
        if not firmware_source.strip():
            QMessageBox.warning(dialog, "No Firmware", "Please select a firmware file or enter URL")
            return
        
        if not device:
            QMessageBox.warning(dialog, "No Device", "Please select a device")
            return
        
        # Create modal progress popup
        self.flash_progress_dialog = QProgressDialog("Initializing...", "Cancel", 0, 0, dialog)
        self.flash_progress_dialog.setWindowTitle("Flashing Firmware")
        self.flash_progress_dialog.setWindowModality(Qt.WindowModal)
        self.flash_progress_dialog.setAutoClose(False)
        self.flash_progress_dialog.setAutoReset(False)
        self.flash_progress_dialog.setMinimumDuration(0)
        self.flash_progress_dialog.setRange(0, 0) # Indeterminate
        self.flash_progress_dialog.show()
        
        # Show progress
        self.flash_progress.setVisible(True)
        self.flash_progress.setValue(0)
        self.flash_status.setText("Preparing to flash...")
        
        # Connect progress signal
        try:
            self.firmware_flasher.progress_update.disconnect(self._on_flash_progress_update)
        except Exception:
            pass
        self.firmware_flasher.progress_update.connect(self._on_flash_progress_update)
        
        try:
            # Start flashing in a separate thread
            self.flash_thread = WorkerThread(
                self._flash_firmware_worker,
                device, firmware_source, erase_flash, verify_flash, boot_mode
            )
            self.flash_thread.succeeded.connect(lambda: self._flash_completed(dialog, True))
            self.flash_thread.error.connect(lambda error: self._flash_completed(dialog, False, error))
            self.flash_thread.start()
            
        except Exception as e:
            if hasattr(self, 'flash_progress_dialog') and self.flash_progress_dialog:
                self.flash_progress_dialog.close()
            QMessageBox.critical(dialog, "Flash Error", f"Failed to start flashing: {str(e)}")
            self.flash_progress.setVisible(False)
    
    def _on_flash_progress_update(self, msg):
        """Handle progress updates for flashing dialog."""
        if hasattr(self, 'flash_status') and self.flash_status:
            self.flash_status.setText(msg)
        if hasattr(self, 'flash_progress') and self.flash_progress:
            val = self.flash_progress.value() + 5
            if val > 100: val = 5
            self.flash_progress.setValue(val)
        if hasattr(self, 'flash_progress_dialog') and self.flash_progress_dialog:
            self.flash_progress_dialog.setLabelText(msg)

    def _flash_firmware_worker(self, device, firmware_source, erase_flash, verify_flash, boot_mode):
        """Worker function for firmware flashing."""
        try:
            # Flash the firmware
            success = self.firmware_flasher.flash_firmware(
                device=device,
                firmware_source=firmware_source,
                progress_callback=None # Use signals instead
            )
            
            if success:
                # Save firmware to OneDrive if enabled
                if self.onedrive_manager.is_enabled():
                    # We can't emit signal directly from here easily without callback, 
                    # but FirmwareFlasher handles flashing signals.
                    # For OneDrive, we might miss progress updates if we don't emit them.
                    # But FirmwareFlasher doesn't know about OneDrive here.
                    # We can use self.firmware_flasher.progress_update.emit() if we wanted, 
                    # but we are in a thread. 
                    # Actually, FirmwareFlasher is a QObject, so emitting its signal from another thread is fine.
                    self.firmware_flasher.progress_update.emit("Saving firmware to OneDrive...")
                    
                    _p = Path(firmware_source)
                    firmware_info = {
                        "name": _p.name,
                        "version": "Unknown",
                        "path": str(_p) if _p.exists() else "",
                        "url": "" if _p.exists() else firmware_source,
                        "size": _p.stat().st_size if _p.exists() else 0,
                        "hash": ""
                    }
                    
                    onedrive_success = self.onedrive_manager.save_firmware_file(
                        operator_name=getattr(self, 'operator_name', type('obj', (object,), {'text': lambda: ''})()).text(),
                        machine_type=getattr(self, 'machine_type', type('obj', (object,), {'currentText': lambda: ''})()).currentText(),
                        machine_id=getattr(self, 'machine_id', type('obj', (object,), {'text': lambda: ''})()).text(),
                        firmware_path=_p if _p.exists() else Path(),
                        firmware_info=firmware_info
                    )
                    
                    if onedrive_success:
                        self.firmware_flasher.progress_update.emit(QCoreApplication.translate("MainWindow", "[SUCCESS] Firmware saved to OneDrive"))
                    else:
                        self.firmware_flasher.progress_update.emit(QCoreApplication.translate("MainWindow", "[WARNING] OneDrive firmware save failed"))
            else:
                raise Exception(QCoreApplication.translate("MainWindow", "Firmware flashing failed"))
                
        except Exception as e:
            raise Exception(QCoreApplication.translate("MainWindow", "Flashing error: {}").format(str(e)))

    def _flash_completed(self, dialog, success: bool, error: str = ""):
        # Close progress popup
        if hasattr(self, 'flash_progress_dialog') and self.flash_progress_dialog:
            self.flash_progress_dialog.close()
            self.flash_progress_dialog = None

        try:
            self.flash_progress.setVisible(False)
            if success:
                self.flash_status.setText(QCoreApplication.translate("MainWindow", "Flash completed"))
                try:
                    self.refresh_devices()
                except Exception:
                    pass
                QMessageBox.information(dialog, QCoreApplication.translate("MainWindow", "Success"), 
                                      QCoreApplication.translate("MainWindow", "Firmware flashed successfully!"))
            else:
                msg = error or QCoreApplication.translate("MainWindow", "Firmware flashing failed")
                self.flash_status.setText(msg)
                QMessageBox.warning(dialog, QCoreApplication.translate("MainWindow", "Failed"), msg)
        except Exception:
            pass
    
    def update_machine_type_combo(self):
        """Update machine type combo box with current config."""
        self.machine_type.clear()
        machine_types = Config.get_machine_types(self.config)
        self.machine_type.addItems(list(machine_types.keys()))
    
    def configure_machine_types_dialog(self):
        """Open machine types configuration dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Machine Types Configuration")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # Machine Types Management Tab
        machine_tab = QWidget()
        machine_tab_layout = QVBoxLayout(machine_tab)
        
        # Scroll area for machine tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        machine_layout = QVBoxLayout(content_widget)
        
        # Machine types list
        list_group = QGroupBox("Machine Types")
        list_layout = QVBoxLayout()
        
        self.machine_types_list = QListWidget()
        self.populate_machine_types_list()
        list_layout.addWidget(self.machine_types_list)
        
        # Machine type buttons
        machine_buttons_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add New")
        add_btn.clicked.connect(lambda: self.add_machine_type_dialog(dialog))
        machine_buttons_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self.edit_machine_type_dialog(dialog))
        machine_buttons_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_machine_type_dialog(dialog))
        machine_buttons_layout.addWidget(delete_btn)
        
        list_layout.addLayout(machine_buttons_layout)
        list_group.setLayout(list_layout)
        machine_layout.addWidget(list_group)
        
        # Machine Types Configuration Guide
        machine_guide_group = QGroupBox("[GUIDE] Machine Types Configuration Guide")
        machine_guide_layout = QVBoxLayout()
        
        # Basic Configuration Guide
        basic_config_guide = QLabel("""
        <b>[CONFIGURATION] Machine Type Configuration:</b><br>
        • <b>Name:</b> Display name for the machine type (e.g., "Amphore", "BOKs")<br>
        • <b>Prefix:</b> Required prefix for machine IDs (e.g., "AMP-", "BOK-")<br>
        • <b>Length:</b> Total length of machine ID including prefix<br><br>
        <b>Example:</b> Name="Amphore", Prefix="AMP-", Length=12 → IDs like "AMP-123456789"
        """)
        basic_config_guide.setWordWrap(True)
        basic_config_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0f8ff; padding: 8px; border-radius: 4px; border: 1px solid #b0d4f1;")
        machine_guide_layout.addWidget(basic_config_guide)
        
        # Best Practices Guide
        best_practices_guide = QLabel("""
        <b>[TIPS] Best Practices:</b><br>
        • Use consistent naming conventions (e.g., all caps for prefixes)<br>
        • Keep prefixes short but meaningful (2-4 characters)<br>
        • Ensure total length accommodates your ID numbering system<br>
        • Test validation before deploying to production<br>
        • Document your machine type standards for your team
        """)
        best_practices_guide.setWordWrap(True)
        best_practices_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff0f0; padding: 8px; border-radius: 4px; border: 1px solid #f1b0b0;")
        machine_guide_layout.addWidget(best_practices_guide)
        
        # Common Examples
        examples_guide = QLabel("""
        <b>[EXAMPLES] Common Examples:</b><br>
        • <b>Water Dispenser:</b> Prefix="WD-", Length=14 → "WD-123456789012"<br>
        • <b>Amphore:</b> Prefix="AMP-", Length=12 → "AMP-123456789"<br>
        • <b>BOKs:</b> Prefix="BOK-", Length=10 → "BOK-1234567"<br>
        • <b>Custom:</b> Prefix="CUST-", Length=15 → "CUST-1234567890"
        """)
        examples_guide.setWordWrap(True)
        examples_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0fff0; padding: 8px; border-radius: 4px; border: 1px solid #b0f1b0;")
        machine_guide_layout.addWidget(examples_guide)
        
        machine_guide_group.setLayout(machine_guide_layout)
        machine_layout.addWidget(machine_guide_group)
        
        # Add stretch to push content up
        machine_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        machine_tab_layout.addWidget(scroll_area)
        
        tab_widget.addTab(machine_tab, QCoreApplication.translate("MainWindow", "Machine Types"))
        
        # Validation Tab
        validation_tab = QWidget()
        validation_layout = QVBoxLayout()
        
        # Test machine ID validation
        test_group = QGroupBox(QCoreApplication.translate("MainWindow", "Test Machine ID Validation"))
        test_layout = QVBoxLayout()
        
        test_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Select machine type and enter ID to test:")))
        
        test_type_layout = QHBoxLayout()
        test_type_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Machine Type:")))
        self.test_machine_type = QComboBox()
        self.test_machine_type.addItems(list(Config.get_machine_types(self.config).keys()))
        test_type_layout.addWidget(self.test_machine_type)
        test_layout.addLayout(test_type_layout)
        
        test_id_layout = QHBoxLayout()
        test_id_layout.addWidget(QLabel(QCoreApplication.translate("MainWindow", "Machine ID:")))
        self.test_machine_id = QLineEdit()
        self.test_machine_id.setPlaceholderText(QCoreApplication.translate("MainWindow", "Enter machine ID to test..."))
        test_id_layout.addWidget(self.test_machine_id)
        test_layout.addLayout(test_id_layout)
        
        test_btn = QPushButton(QCoreApplication.translate("MainWindow", "Test Validation"))
        test_btn.clicked.connect(self.test_machine_id_validation)
        test_layout.addWidget(test_btn)
        
        self.validation_result = QLabel(QCoreApplication.translate("MainWindow", "Enter a machine ID to test validation"))
        self.validation_result.setStyleSheet("color: #666; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        test_layout.addWidget(self.validation_result)
        
        test_group.setLayout(test_layout)
        validation_layout.addWidget(test_group)
        
        validation_tab.setLayout(validation_layout)
        tab_widget.addTab(validation_tab, QCoreApplication.translate("MainWindow", "Validation Test"))
        
        layout.addWidget(tab_widget)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec():
            # Refresh machine type combo in main window
            self.update_machine_type_combo()
            # Update machine ID placeholder
            current_type = self.machine_type.currentText()
            self.on_machine_type_changed(current_type)
    
    def populate_machine_types_list(self):
        """Populate the machine types list widget."""
        self.machine_types_list.clear()
        machine_types = Config.get_machine_types(self.config)
        
        for name, config in machine_types.items():
            item_text = f"{name} - Prefix: '{config['prefix']}' - Length: {config['length']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, name)
            self.machine_types_list.addItem(item)
    
    def add_machine_type_dialog(self, parent_dialog):
        """Open dialog to add new machine type."""
        dialog = QDialog(parent_dialog)
        dialog.setWindowTitle("Add Machine Type")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Name
        layout.addWidget(QLabel("Machine Type Name:"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g., NewMachine")
        layout.addWidget(name_input)
        
        # Prefix
        layout.addWidget(QLabel("ID Prefix:"))
        prefix_input = QLineEdit()
        prefix_input.setPlaceholderText("e.g., NM-")
        layout.addWidget(prefix_input)
        
        # Length
        layout.addWidget(QLabel("Total ID Length:"))
        length_input = QSpinBox()
        length_input.setRange(3, 50)
        length_input.setValue(10)
        layout.addWidget(length_input)
        
        # Preview
        preview_label = QLabel("Preview: NM-1234567")
        preview_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(preview_label)
        
        def update_preview():
            prefix = prefix_input.text() or "XX-"
            length = length_input.value()
            remaining = length - len(prefix)
            if remaining > 0:
                preview = prefix + "X" * remaining
                preview_label.setText(f"Preview: {preview}")
            else:
                preview_label.setText("Invalid: Length must be greater than prefix length")
        
        prefix_input.textChanged.connect(update_preview)
        length_input.valueChanged.connect(update_preview)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec():
            name = name_input.text().strip()
            prefix = prefix_input.text().strip()
            length = length_input.value()
            
            if not name or not prefix:
                QMessageBox.warning(dialog, "Invalid Input", "Name and prefix are required")
                return
            
            if length <= len(prefix):
                QMessageBox.warning(dialog, "Invalid Length", "Total length must be greater than prefix length")
                return
            
            # Add to config
            self.config = Config.add_machine_type(self.config, name, prefix, length)
            Config.save_config(self.config)
            
            # Refresh lists
            self.populate_machine_types_list()
            QMessageBox.information(dialog, "Success", f"Machine type '{name}' added successfully!")
    
    def edit_machine_type_dialog(self, parent_dialog):
        """Open dialog to edit machine type."""
        current_item = self.machine_types_list.currentItem()
        if not current_item:
            QMessageBox.warning(parent_dialog, "No Selection", "Please select a machine type to edit")
            return
        
        old_name = current_item.data(Qt.UserRole)
        machine_types = Config.get_machine_types(self.config)
        old_config = machine_types[old_name]
        
        dialog = QDialog(parent_dialog)
        dialog.setWindowTitle(f"Edit Machine Type: {old_name}")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Name
        layout.addWidget(QLabel("Machine Type Name:"))
        name_input = QLineEdit()
        name_input.setText(old_name)
        layout.addWidget(name_input)
        
        # Prefix
        layout.addWidget(QLabel("ID Prefix:"))
        prefix_input = QLineEdit()
        prefix_input.setText(old_config['prefix'])
        layout.addWidget(prefix_input)
        
        # Length
        layout.addWidget(QLabel("Total ID Length:"))
        length_input = QSpinBox()
        length_input.setRange(3, 50)
        length_input.setValue(old_config['length'])
        layout.addWidget(length_input)
        
        # Preview
        preview_label = QLabel()
        layout.addWidget(preview_label)
        
        def update_preview():
            prefix = prefix_input.text() or "XX-"
            length = length_input.value()
            remaining = length - len(prefix)
            if remaining > 0:
                preview = prefix + "X" * remaining
                preview_label.setText(f"Preview: {preview}")
                preview_label.setStyleSheet("color: #666; font-style: italic;")
            else:
                preview_label.setText("Invalid: Length must be greater than prefix length")
                preview_label.setStyleSheet("color: red; font-style: italic;")
        
        prefix_input.textChanged.connect(update_preview)
        length_input.valueChanged.connect(update_preview)
        update_preview()  # Initial update
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec():
            new_name = name_input.text().strip()
            prefix = prefix_input.text().strip()
            length = length_input.value()
            
            if not new_name or not prefix:
                QMessageBox.warning(dialog, "Invalid Input", "Name and prefix are required")
                return
            
            if length <= len(prefix):
                QMessageBox.warning(dialog, "Invalid Length", "Total length must be greater than prefix length")
                return
            
            # Update config
            self.config = Config.update_machine_type(self.config, old_name, new_name, prefix, length)
            Config.save_config(self.config)
            
            # Refresh lists
            self.populate_machine_types_list()
            QMessageBox.information(dialog, "Success", f"Machine type updated successfully!")
    
    def delete_machine_type_dialog(self, parent_dialog):
        """Delete machine type with confirmation."""
        current_item = self.machine_types_list.currentItem()
        if not current_item:
            QMessageBox.warning(parent_dialog, "No Selection", "Please select a machine type to delete")
            return
        
        name = current_item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            parent_dialog, 
            "Confirm Delete", 
            f"Are you sure you want to delete the machine type '{name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Delete from config
            self.config = Config.delete_machine_type(self.config, name)
            Config.save_config(self.config)
            
            # Refresh lists
            self.populate_machine_types_list()
            QMessageBox.information(parent_dialog, "Success", f"Machine type '{name}' deleted successfully!")
    
    def test_machine_id_validation(self):
        """Test machine ID validation."""
        machine_type_name = self.test_machine_type.currentText()
        machine_id = self.test_machine_id.text().strip()
        
        if not machine_id:
            self.validation_result.setText("Please enter a machine ID to test")
            self.validation_result.setStyleSheet("color: #666; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
            return
        
        machine_types = Config.get_machine_types(self.config)
        machine_type_config = machine_types.get(machine_type_name)
        
        if not machine_type_config:
            self.validation_result.setText("Error: Machine type configuration not found")
            self.validation_result.setStyleSheet("color: red; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
            return
        
        is_valid, message = Config.validate_machine_id(machine_id, machine_type_config)
        
        if is_valid:
            self.validation_result.setText(f"[SUCCESS] Valid: {message}")
            self.validation_result.setStyleSheet("color: green; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        else:
            self.validation_result.setText(f"[INVALID] Invalid: {message}")
            self.validation_result.setStyleSheet("color: red; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
    
    def configure_onedrive_dialog(self):
        """Open OneDrive configuration dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("OneDrive Configuration")
        dialog.setWindowState(Qt.WindowMaximized)
        
        layout = QVBoxLayout()
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # OneDrive Settings Tab
        settings_tab = QWidget()
        settings_tab_layout = QVBoxLayout(settings_tab)
        
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.NoFrame)
        
        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)

        # Status banner at the top
        self.onedrive_status_banner = QLabel("OneDrive enabled: please test and save settings")
        self.onedrive_status_banner.setWordWrap(True)
        self.onedrive_status_banner.setStyleSheet("background:#cff4fc;color:#055160;padding:10px;border:1px solid #b6effb;border-radius:6px;")
        settings_layout.addWidget(self.onedrive_status_banner)
        
        # Enable OneDrive
        enable_group = QGroupBox("OneDrive Integration")
        enable_layout = QVBoxLayout()
        
        self.onedrive_enabled = QCheckBox("Enable OneDrive Integration")
        self.onedrive_enabled.setChecked(self.config.get('onedrive', {}).get('enabled', False))
        self.onedrive_enabled.setToolTip("Turn on OneDrive features for saving machine data and firmware history.")
        self.onedrive_enabled.stateChanged.connect(self._validate_onedrive_inputs)
        enable_layout.addWidget(self.onedrive_enabled)
        
        enable_group.setLayout(enable_layout)
        settings_layout.addWidget(enable_group)
        
        # OneDrive Path Configuration
        path_group = QGroupBox("OneDrive Folder Configuration")
        path_layout = QVBoxLayout()
        
        # Base folder path
        path_layout.addWidget(QLabel("OneDrive Shared Folder Path:"))
        folder_layout = QHBoxLayout()
        self.onedrive_folder_path = QLineEdit()
        self.onedrive_folder_path.setText(self.config.get('onedrive', {}).get('folder_path', ''))
        self.onedrive_folder_path.setPlaceholderText("e.g., C:\\Users\\Username\\OneDrive\\SharedFolder")
        self.onedrive_folder_path.setToolTip("The root folder where user/machine subfolders will be created.")
        self.onedrive_folder_path.textChanged.connect(self._validate_onedrive_inputs)
        folder_layout.addWidget(self.onedrive_folder_path)
        
        detect_btn = QPushButton("Detect")
        detect_btn.setToolTip("Auto-detect your OneDrive folder from common locations.")
        detect_btn.clicked.connect(self._detect_onedrive_folder)
        folder_layout.addWidget(detect_btn)

        browse_folder_btn = QPushButton("Browse")
        browse_folder_btn.clicked.connect(self._browse_onedrive_folder)
        folder_layout.addWidget(browse_folder_btn)

        open_btn = QPushButton("Open")
        open_btn.setToolTip("Open the selected folder in Explorer.")
        open_btn.clicked.connect(self._open_onedrive_folder)
        folder_layout.addWidget(open_btn)
        path_layout.addLayout(folder_layout)

        # Inline path error
        self.onedrive_path_error = QLabel("")
        self.onedrive_path_error.setStyleSheet("color:red;font-size:11px")
        path_layout.addWidget(self.onedrive_path_error)
        
        # User folder name
        path_layout.addWidget(QLabel("User Folder Name:"))
        self.user_folder_name = QLineEdit()
        self.user_folder_name.setText(self.config.get('onedrive', {}).get('user_folder', ''))
        self.user_folder_name.setPlaceholderText("e.g., JohnDoe_Work")
        self.user_folder_name.setToolTip("Your personal subfolder under the shared OneDrive path (e.g., JohnDoe_Work).")
        self.user_folder_name.textChanged.connect(self._validate_onedrive_inputs)
        path_layout.addWidget(self.user_folder_name)

        # Inline user folder error
        self.user_folder_error = QLabel("")
        self.user_folder_error.setStyleSheet("color:red;font-size:11px")
        path_layout.addWidget(self.user_folder_error)
        
        path_group.setLayout(path_layout)
        settings_layout.addWidget(path_group)
        
        # Sync Options
        sync_group = QGroupBox("Sync Options")
        sync_layout = QVBoxLayout()
        
        self.auto_create_folders = QCheckBox("Automatically create folder structure")
        self.auto_create_folders.setChecked(self.config.get('onedrive', {}).get('auto_create_folders', True))
        sync_layout.addWidget(self.auto_create_folders)
        
        self.sync_enabled = QCheckBox("Enable automatic sync")
        self.sync_enabled.setChecked(self.config.get('onedrive', {}).get('sync_enabled', True))
        sync_layout.addWidget(self.sync_enabled)
        
        sync_group.setLayout(sync_layout)
        settings_layout.addWidget(sync_group)
        
        # Test Connection
        test_group = QGroupBox("Test Connection")
        test_layout = QVBoxLayout()
        
        test_btn = QPushButton("Test OneDrive Connection")
        test_btn.clicked.connect(self.test_onedrive_connection)
        test_layout.addWidget(test_btn)
        
        self.onedrive_test_result = QLabel("Click 'Test Connection' to verify OneDrive access")
        self.onedrive_test_result.setStyleSheet("color: #666; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        test_layout.addWidget(self.onedrive_test_result)
        
        test_group.setLayout(test_layout)
        settings_layout.addWidget(test_group)
        
        # OneDrive Configuration Guide (Collapsible & Scrollable)
        toggle_guide_btn = QPushButton("Show OneDrive Guide")
        toggle_guide_btn.setCheckable(True)
        toggle_guide_btn.setChecked(False)
        settings_layout.addWidget(toggle_guide_btn)

        onedrive_guide_group = QGroupBox("[GUIDE] OneDrive Configuration Guide")
        onedrive_guide_group.setVisible(False)
        
        def update_guide_btn_text(checked):
            toggle_guide_btn.setText("Hide OneDrive Guide" if checked else "Show OneDrive Guide")
            
        toggle_guide_btn.toggled.connect(onedrive_guide_group.setVisible)
        toggle_guide_btn.toggled.connect(update_guide_btn_text)

        onedrive_guide_layout = QVBoxLayout()
        
        # Scroll Area for guide content
        guide_scroll = QScrollArea()
        guide_scroll.setWidgetResizable(True)
        guide_scroll.setFrameShape(QFrame.NoFrame)
        guide_scroll.setMaximumHeight(300)
        
        guide_content = QWidget()
        guide_content_layout = QVBoxLayout(guide_content)
        guide_content_layout.setContentsMargins(0, 0, 0, 0)
        
        # OneDrive Setup Guide
        onedrive_setup_guide = QLabel("""
        <b>[ONEDRIVE] OneDrive Setup:</b><br>
        1. Install OneDrive: <a href="https://www.microsoft.com/en-us/microsoft-365/onedrive/download">Download OneDrive</a><br>
        2. Sign in to your Microsoft account<br>
        3. Create a shared folder or use existing OneDrive folder<br>
        4. Copy the full path to your OneDrive folder<br>
        5. Test the connection to verify access
        """)
        onedrive_setup_guide.setOpenExternalLinks(True)
        onedrive_setup_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0f8ff; padding: 8px; border-radius: 4px; border: 1px solid #b0d4f1;")
        guide_content_layout.addWidget(onedrive_setup_guide)
        
        # Alternative Cloud Services
        cloud_alternatives_guide = QLabel("""
        <b>[ALTERNATIVES] Alternative Cloud Services:</b><br>
        • <b>Google Drive:</b> <a href="https://drive.google.com">drive.google.com</a> - Use Google Drive folder path<br>
        • <b>Dropbox:</b> <a href="https://www.dropbox.com">dropbox.com</a> - Use Dropbox folder path<br>
        • <b>iCloud:</b> <a href="https://www.icloud.com">icloud.com</a> - Use iCloud folder path<br>
        • <b>Network Drive:</b> Use UNC path (\\\\server\\share) for network storage
        """)
        cloud_alternatives_guide.setOpenExternalLinks(True)
        cloud_alternatives_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff0f0; padding: 8px; border-radius: 4px; border: 1px solid #f1b0b0;")
        guide_content_layout.addWidget(cloud_alternatives_guide)
        
        # Troubleshooting
        onedrive_troubleshooting_guide = QLabel("""
        <b>[TROUBLESHOOTING] OneDrive Troubleshooting:</b><br>
        • <b>Access Denied:</b> Check folder permissions and sharing settings<br>
        • <b>Path Not Found:</b> Verify the folder path exists and is accessible<br>
        • <b>Sync Issues:</b> Ensure OneDrive is running and synced<br>
        • <b>Network Issues:</b> Check internet connection and firewall settings<br>
        • <b>Still having issues?</b> Try: <a href="https://support.microsoft.com/en-us/onedrive">OneDrive Support</a>
        """)
        onedrive_troubleshooting_guide.setOpenExternalLinks(True)
        onedrive_troubleshooting_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff8f0; padding: 8px; border-radius: 4px; border: 1px solid #f1d0b0;")
        guide_content_layout.addWidget(onedrive_troubleshooting_guide)
        
        guide_scroll.setWidget(guide_content)
        onedrive_guide_layout.addWidget(guide_scroll)
        
        onedrive_guide_group.setLayout(onedrive_guide_layout)
        settings_layout.addWidget(onedrive_guide_group)
        
        settings_scroll.setWidget(settings_content)
        settings_tab_layout.addWidget(settings_scroll)
        tab_widget.addTab(settings_tab, "Settings")
        
        # Folder Structure Tab
        structure_tab = QWidget()
        structure_layout = QVBoxLayout()
        
        # Folder structure explanation
        structure_info = QLabel("""
        <b>OneDrive Folder Structure:</b><br><br>
        
        <b>Base Folder:</b> {OneDrive Shared Folder}<br>
        ├── <b>User Folder:</b> {User Name}_Work<br>
        │   ├── <b>Machine Type Folder:</b> {Machine Type}<br>
        │   │   ├── <b>Machine ID Folder:</b> {Machine ID}<br>
        │   │   │   ├── <b>Machine Data:</b> {Machine ID}_data.json<br>
        │   │   │   └── <b>Firmware Folder:</b> firmware/<br>
        │   │   │       ├── <b>Firmware Files:</b> {timestamp}_{firmware}.bin<br>
        │   │   │       └── <b>Firmware Info:</b> {timestamp}_firmware_info.json<br>
        │   │   └── <b>Another Machine:</b> {Another Machine ID}/<br>
        │   └── <b>Another Machine Type:</b> {Another Type}/<br>
        └── <b>Another User:</b> {Another User}_Work/<br><br>
        
        <b>Example:</b><br>
        OneDrive/SharedFolder/<br>
        ├── JohnDoe_Work/<br>
        │   ├── Amphore/<br>
        │   │   ├── AMP-1234567890/<br>
        │   │   │   ├── AMP-1234567890_data.json<br>
        │   │   │   └── firmware/<br>
        │   │   │       ├── 20241028_143022_firmware_v2.1.bin<br>
        │   │   │       └── 20241028_143022_firmware_info.json<br>
        │   │   └── AMP-0987654321/<br>
        │   └── BOKs/<br>
        │       └── BOK-12345678/<br>
        └── JaneSmith_Work/<br>
        """)
        structure_info.setStyleSheet("color: #333; font-size: 11px; background: #f9f9f9; padding: 15px; border-radius: 5px; border: 1px solid #ddd;")
        structure_layout.addWidget(structure_info)
        
        structure_tab.setLayout(structure_layout)
        tab_widget.addTab(structure_tab, "Folder Structure")
        
        # Machine History Tab
        history_tab = QWidget()
        history_layout = QVBoxLayout()
        
        # Machine history list
        history_group = QGroupBox("Machine History")
        history_list_layout = QVBoxLayout()
        
        self.machine_history_list = QListWidget()
        self.populate_machine_history()
        history_list_layout.addWidget(self.machine_history_list)
        
        refresh_history_btn = QPushButton("Refresh History")
        refresh_history_btn.clicked.connect(self.populate_machine_history)
        history_list_layout.addWidget(refresh_history_btn)
        
        history_group.setLayout(history_list_layout)
        history_layout.addWidget(history_group)
        
        history_tab.setLayout(history_layout)
        tab_widget.addTab(history_tab, "Machine History")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.onedrive_buttons = buttons
        buttons.accepted.connect(lambda: self.save_onedrive_settings(dialog))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        # Initial validation and banner
        self._validate_onedrive_inputs()

        if dialog.exec():
            pass  # Settings saved
    
    def _browse_onedrive_folder(self):
        """Browse for OneDrive folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select OneDrive Shared Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder_path:
            self.onedrive_folder_path.setText(folder_path)
            self._validate_onedrive_inputs()

    def _detect_onedrive_folder(self):
        """Attempt to detect OneDrive base folder from common locations."""
        try:
            candidates = []
            # Environment variables commonly set by OneDrive
            for env_key in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
                p = os.environ.get(env_key)
                if p:
                    candidates.append(Path(p))

            # Common home subfolders
            home = Path.home()
            try:
                for child in home.iterdir():
                    if child.is_dir() and child.name.startswith("OneDrive"):
                        candidates.append(child)
            except Exception:
                pass

            # Prefer an existing folder
            chosen = None
            for c in candidates:
                try:
                    if c.exists() and c.is_dir():
                        chosen = c
                        break
                except Exception:
                    continue

            if chosen:
                self.onedrive_folder_path.setText(str(chosen))
                self._validate_onedrive_inputs()
                QMessageBox.information(self, "Detected", f"Detected OneDrive folder: {chosen}")
            else:
                QMessageBox.warning(self, "Not Found", "Could not auto-detect a OneDrive folder. Please browse manually.")
        except Exception as e:
            QMessageBox.warning(self, "Detection Error", f"Failed to detect OneDrive folder: {e}")

    def _open_onedrive_folder(self):
        """Open current OneDrive folder in Explorer if valid."""
        try:
            p = self.onedrive_folder_path.text().strip()
            if p:
                os.startfile(p)
        except Exception as e:
            QMessageBox.warning(self, "Open Folder", f"Failed to open folder: {e}")
    
    def test_onedrive_connection(self):
        """Test OneDrive connection."""
        # Update config temporarily for testing
        temp_config = self.config.copy()
        temp_config['onedrive'] = {
            'enabled': self.onedrive_enabled.isChecked(),
            'folder_path': self.onedrive_folder_path.text(),
            'user_folder': self.user_folder_name.text(),
            'sync_enabled': self.sync_enabled.isChecked(),
            'auto_create_folders': self.auto_create_folders.isChecked()
        }
        
        # Create temporary OneDrive manager for testing
        temp_manager = OneDriveManager()
        temp_manager.config = temp_config
        
        success, message = temp_manager.test_connection()
        
        if success:
            self.onedrive_test_result.setText(f"[SUCCESS] {message}")
            self.onedrive_test_result.setStyleSheet("color:#0f5132;font-size:12px;padding:10px;border:1px solid #badbcc;border-radius:6px;background:#d1e7dd;")
            self._update_onedrive_status_banner(enabled=self.onedrive_enabled.isChecked(), ok=True, text="OneDrive connected")
            self._update_onedrive_status_indicator()
        else:
            self.onedrive_test_result.setText(f"[ERROR] {message}")
            self.onedrive_test_result.setStyleSheet("color:#842029;font-size:12px;padding:10px;border:1px solid #f5c2c7;border-radius:6px;background:#f8d7da;")
            self._update_onedrive_status_banner(enabled=self.onedrive_enabled.isChecked(), ok=False, text="Connection failed")
            self._update_onedrive_status_indicator()
    
    def save_onedrive_settings(self, dialog):
        """Save OneDrive settings."""
        self.config['onedrive'] = {
            'enabled': self.onedrive_enabled.isChecked(),
            'folder_path': self.onedrive_folder_path.text(),
            'user_folder': self.user_folder_name.text(),
            'sync_enabled': self.sync_enabled.isChecked(),
            'auto_create_folders': self.auto_create_folders.isChecked()
        }
        
        Config.save_config(self.config)
        
        # Update OneDrive manager
        self.onedrive_manager.config = self.config
        
        QMessageBox.information(dialog, "Settings Saved", "OneDrive configuration saved successfully!")
        self._update_onedrive_status_banner(enabled=self.onedrive_enabled.isChecked(), ok=None, text="Settings updated")
        self._update_onedrive_status_indicator()
    
    def populate_machine_history(self):
        """Populate machine history list."""
        self.machine_history_list.clear()
        
        if not self.onedrive_manager.is_enabled():
            item = QListWidgetItem("OneDrive integration is disabled")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.machine_history_list.addItem(item)
            return
        
        machines = self.onedrive_manager.list_machines()
        
        if not machines:
            item = QListWidgetItem("No machines found in OneDrive")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.machine_history_list.addItem(item)
            return
        
        for machine in machines:
            timestamp = machine.get('timestamp', 'Unknown')
            item_text = f"{machine['machine_type']} - {machine['machine_id']} ({machine['operator_name']}) - {timestamp}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, machine)
            self.machine_history_list.addItem(item)

    def _validate_onedrive_inputs(self):
        """Validate inputs and update button state + banner."""
        enabled = self.onedrive_enabled.isChecked()
        folder = self.onedrive_folder_path.text().strip()
        user = self.user_folder_name.text().strip()

        path_ok = True
        user_ok = True

        if hasattr(self, 'onedrive_path_error') and hasattr(self, 'user_folder_error'):
            self.onedrive_path_error.setText("")
            self.user_folder_error.setText("")

        if enabled:
            if not folder:
                if hasattr(self, 'onedrive_path_error'):
                    self.onedrive_path_error.setText("Please provide a OneDrive folder path.")
                path_ok = False
            else:
                try:
                    if not Path(folder).exists():
                        if hasattr(self, 'onedrive_path_error'):
                            self.onedrive_path_error.setText("Folder does not exist.")
                        path_ok = False
                except Exception:
                    if hasattr(self, 'onedrive_path_error'):
                        self.onedrive_path_error.setText("Invalid folder path.")
                    path_ok = False

            if not user:
                if hasattr(self, 'user_folder_error'):
                    self.user_folder_error.setText("Please provide a user folder name.")
                user_ok = False
            else:
                if any(ch in user for ch in ['\\\
','/', ':', '*', '?', '"', '<', '>', '|']):
                    if hasattr(self, 'user_folder_error'):
                        self.user_folder_error.setText("User folder name contains invalid characters.")
                    user_ok = False

        # Enable/disable OK button
        if hasattr(self, 'onedrive_buttons'):
            ok_button = self.onedrive_buttons.button(QDialogButtonBox.Ok)
            ok_button.setEnabled((not enabled) or (path_ok and user_ok))

        # Update status banner
        self._update_onedrive_status_banner(enabled=enabled, ok=(path_ok and user_ok) if enabled else None)

    def _update_onedrive_status_banner(self, enabled: bool, ok: Optional[bool] = None, text: Optional[str] = None):
        """Update the top status banner color and message."""
        if not enabled:
            self.onedrive_status_banner.setText(text or "OneDrive is currently disabled")
            self.onedrive_status_banner.setStyleSheet("background:#fff3cd;color:#664d03;padding:10px;border:1px solid #ffe69c;border-radius:6px;")
            return

        if ok is True:
            self.onedrive_status_banner.setText(text or "OneDrive ready: configuration looks valid")
            self.onedrive_status_banner.setStyleSheet("background:#d1e7dd;color:#0f5132;padding:10px;border:1px solid #badbcc;border-radius:6px;")
        elif ok is False:
            self.onedrive_status_banner.setText(text or "OneDrive misconfigured: please fix highlighted fields")
            self.onedrive_status_banner.setStyleSheet("background:#f8d7da;color:#842029;padding:10px;border:1px solid #f5c2c7;border-radius:6px;")
        else:
            self.onedrive_status_banner.setText(text or "OneDrive enabled: please test and save settings")
            self.onedrive_status_banner.setStyleSheet("background:#cff4fc;color:#055160;padding:10px;border:1px solid #b6effb;border-radius:6px;")

    def _update_onedrive_status_indicator(self):
        try:
            enabled = self.onedrive_manager.is_enabled()
            txt = QCoreApplication.translate("MainWindow", "OneDrive: On") if enabled else QCoreApplication.translate("MainWindow", "OneDrive: Off")
            self.onedrive_status_label.setText(txt)
        except Exception:
            pass

    def apply_device_filter(self):
        try:
            query = (self.filter_input.text() or "").lower().strip()
            type_sel = self.filter_type_combo.currentText()
            src = list(self.devices)
            def match(d):
                if type_sel and type_sel != QCoreApplication.translate("MainWindow", "All"):
                    if d.board_type.value != type_sel:
                        return False
                if not query:
                    return True
                hay = " ".join([
                    d.get_display_name() or "",
                    d.port or "",
                    d.board_type.value or "",
                ]).lower()
                return query in hay
            self.filtered_devices = [d for d in src if match(d)]
            self.update_device_table()
        except Exception:
            self.filtered_devices = list(self.devices)
            self.update_device_table()
    
    def save_operator_info(self):
        """Save operator information to config."""
        self.config['operator'] = {
            'name': self.operator_name.text(),
            'email': self.operator_email.text(),
            'phone': getattr(self, 'operator_phone', QLineEdit()).text() if hasattr(self, 'operator_phone') else '',
            'country': getattr(self, 'operator_country', QLineEdit()).text() if hasattr(self, 'operator_country') else ''
        }
        self.config['machine_type'] = self.machine_type.currentText()
        # Also persist current machine ID and suffix
        try:
            self.config['machine_id'] = self.machine_id.text()
            self.config['machine_id_suffix'] = self.machine_id_suffix.currentText().strip()
        except Exception:
            pass
        Config.save_config(self.config)

    def _detect_country_name(self) -> str:
        try:
            loc = locale.getdefaultlocale()[0] or ''
        except Exception:
            loc = ''
        if loc and '_' in loc:
            code = loc.split('_')[-1].upper()
            name = self.COUNTRY_NAMES.get(code)
            if name:
                return name
            return code
        return ''

    def _get_detected_country_from_footer(self) -> str:
        try:
            city, country = get_location()
            return country or ''
        except Exception:
            return ''
    
    def center_window(self):
        """Center the window on the primary screen."""
        from PySide6.QtWidgets import QApplication
        
        screen = QApplication.primaryScreen().geometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)
    
    def log(self, message: str):
        """Log a message without a visible logs panel."""
        try:
            self._show_status(message[:120])
        except Exception:
            pass
        try:
            if hasattr(self, 'log_area') and self.log_area:
                self.log_area.append(message)
        except Exception:
            pass
        logger.info(message)
    
    def show_first_run_dialog(self):
        """Show first run setup dialog with quick-access to documentation."""
        manager = BootstrapManager()
        success, warnings = manager.run_first_run_setup()

        # Build the dialog
        dlg = QDialog(self)
        dlg.setWindowTitle(QCoreApplication.translate("MainWindow", "Welcome to AWG Kumulus"))
        layout = QVBoxLayout()

        # Intro text
        intro = QLabel(QCoreApplication.translate(
            "MainWindow",
            "Setup completed. You can open the README, USAGE guide, or the full user manual (English or French)."
        ))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if warnings:
            msg = "\n".join(warnings)
            warn = QLabel(QCoreApplication.translate("MainWindow", "Warnings:"))
            layout.addWidget(warn)
            warn_text = QTextEdit()
            warn_text.setReadOnly(True)
            warn_text.setText(msg)
            warn_text.setMinimumHeight(80)
            layout.addWidget(warn_text)

        # Buttons row
        buttons = QDialogButtonBox()
        btn_readme = buttons.addButton(QCoreApplication.translate("MainWindow", "Open README"), QDialogButtonBox.ActionRole)
        btn_usage = buttons.addButton(QCoreApplication.translate("MainWindow", "Open USAGE"), QDialogButtonBox.ActionRole)
        btn_manual_en = buttons.addButton(QCoreApplication.translate("MainWindow", "Manual (English)"), QDialogButtonBox.ActionRole)
        btn_manual_fr = buttons.addButton(QCoreApplication.translate("MainWindow", "Manuel (Français)"), QDialogButtonBox.ActionRole)
        btn_close = buttons.addButton(QDialogButtonBox.Close)
        layout.addWidget(buttons)

        # Hook up actions
        def _project_root():
            # Resolve project root when running from source (…/DesktopApp)
            try:
                return Path(__file__).resolve().parents[2]
            except Exception:
                return Path.cwd()

        def _exe_dir():
            # Directory of the running executable or script
            try:
                return Path(sys.argv[0]).resolve().parent
            except Exception:
                return Path.cwd()

        def _meipass_dir():
            # PyInstaller onefile temp extraction dir
            try:
                base = getattr(sys, "_MEIPASS", None)
                return Path(base) if base else None
            except Exception:
                return None

        def open_readme():
            candidates = [
                _project_root() / "README.md",
                _exe_dir() / "README.md",
                _project_root() / "release" / "Windows" / "INSTALL_README.txt",
            ]
            for p in candidates:
                if p.exists():
                    self._open_document_file(p)
                    return
            QMessageBox.warning(self, "README", "README file not found.")

        def open_usage():
            candidates = [
                _project_root() / "release" / "USAGE.md",
                _project_root() / "release" / "Windows" / "USAGE.md",
                _exe_dir() / "USAGE.md",
                (_meipass_dir() / "USAGE.md") if _meipass_dir() else None,
            ]
            for p in candidates:
                if p.exists():
                    self._open_document_file(p)
                    return
            QMessageBox.warning(self, "USAGE", "USAGE guide not found.")

        def open_manual_en():
            self._open_manual("en")

        def open_manual_fr():
            self._open_manual("fr")

        btn_readme.clicked.connect(open_readme)
        btn_usage.clicked.connect(open_usage)
        btn_manual_en.clicked.connect(open_manual_en)
        btn_manual_fr.clicked.connect(open_manual_fr)
        btn_close.clicked.connect(dlg.close)

        dlg.setLayout(layout)
        dlg.exec()
    
    def check_first_run_tour(self):
        """Check if tour needs to run automatically."""
        try:
            if not self.config.get('tour_seen', False):
                # Delay to ensure UI is ready
                QTimer.singleShot(1000, self.show_quick_tour_dialog)
                self.config['tour_seen'] = True
                Config.save_config(self.config)
        except Exception as e:
            logger.warning(f"Failed to check first run tour: {e}")

    def show_quick_tour_dialog(self):
        """Start the interactive tour."""
        try:
            if hasattr(self, 'tour_manager'):
                self.tour_manager.start_tour()
            else:
                self.tour_manager = TourManager(self)
                self.tour_manager.start_tour()
        except Exception as e:
            logger.error(f"Failed to start tour: {e}")
            QMessageBox.warning(self, "Tour Error", f"Could not start tour: {e}")

    def _open_document_file(self, path: Path):
        """Open a local document file using the OS default handler."""
        try:
            url = QUrl.fromLocalFile(str(path))
            QDesktopServices.openUrl(url)
        except Exception as e:
            QMessageBox.warning(self, "Open Document", f"Failed to open {path}: {e}")

    def _open_manual(self, lang: str):
        """Open localized HTML manual from docs/manual (handles dev and installed)."""
        lang = (lang or "en").lower()
        is_fr = lang.startswith("fr")

        def _project_root():
            try:
                return Path(__file__).resolve().parents[2]
            except Exception:
                return Path.cwd()

        def _exe_dir():
            try:
                return Path(sys.argv[0]).resolve().parent
            except Exception:
                return Path.cwd()

        def _meipass_dir():
            try:
                base = getattr(sys, "_MEIPASS", None)
                return Path(base) if base else None
            except Exception:
                return None

        filenames = ["user_manual_fr.html" if is_fr else "user_manual_en.html"]
        candidates = [
            _project_root() / "docs" / "manual" / filenames[0],
            _exe_dir() / "docs" / "manual" / filenames[0],
            (_meipass_dir() / "docs" / "manual" / filenames[0]) if _meipass_dir() else None,
        ]
        for p in candidates:
            if p and p.exists():
                self._open_document_file(p)
                return
        QMessageBox.warning(self, "Manual", "Manual not found in expected locations.")

    def open_user_manual_current_lang(self):
        """Open manual based on current UI language."""
        try:
            lang = self.translation_manager.get_language_code()
        except Exception:
            lang = "en"
        self._open_manual(lang)
    
    def _device_change_callback(self, event_type: str, device: Device):
        """Handle device changes from background thread using Qt signals."""
        if event_type == "device_connected":
            # Use QTimer to safely update GUI from main thread
            QTimer.singleShot(0, lambda: self._handle_device_connected(device))
        elif event_type == "device_disconnected":
            # Use QTimer to safely update GUI from main thread
            QTimer.singleShot(0, lambda: self._handle_device_disconnected(device))
    
    def _handle_device_connected(self, device: Device):
        """Handle device connection in main thread."""
        self.log(f"[CONNECTED] Device connected: {device.get_display_name()}")
        self.refresh_devices()  # Refresh the device table
        try:
            self._update_footer_devices()
        except Exception:
            pass
        try:
            self._auto_flash_on_connect(device)
        except Exception as e:
            self.log(f"Auto-flash skipped: {e}")
    
    def _handle_device_disconnected(self, device: Device):
        """Handle device disconnection in main thread."""
        self.log(f"[DISCONNECTED] Device disconnected: {device.get_display_name()}")
        self.refresh_devices()  # Refresh the device table
        try:
            self._update_footer_devices()
        except Exception:
            pass

    def _update_footer_devices(self):
        """Update the footer devices count label."""
        try:
            # Prefer statistics from detector, fallback to current list
            stats = self.device_detector.get_device_statistics() if hasattr(self, 'device_detector') else None
            if stats:
                total = stats.get('total_devices', 0)
                connected = stats.get('connected_devices', 0)
                disconnected = stats.get('disconnected_devices', max(0, total - connected))
            else:
                devices = getattr(self, 'devices', []) or []
                total = len(devices)
                connected = sum(1 for d in devices if getattr(d, 'status', '') == 'Connected')
                disconnected = max(0, total - connected)

            self.footer_devices_label.setText(
                f"🔌 Connected: {connected} · Disconnected: {disconnected} · Total: {total}"
            )
        except Exception:
            count = len(getattr(self, 'devices', []) or [])
            self.footer_devices_label.setText(f"🔌 Devices found: {count}")
    
    def on_theme_changed(self, theme_name: str):
        """Handle theme change."""
        self.log(f"[THEME] Theme changed to: {theme_name}")
        # Apply additional stylesheet if needed
        app = QApplication.instance()
        if app:
            stylesheet = self.theme_manager.get_theme_stylesheet(ThemeType(theme_name.split('_')[0]))
            app.setStyleSheet(stylesheet)
    
    def update_ui_text(self):
        """Update UI text with current language using Qt translation."""
        # Update window title
        self.setWindowTitle(QCoreApplication.translate("MainWindow", "AWG Kumulus Device Manager v1.0.0"))
        
        # Update main buttons
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.setText(QCoreApplication.translate('MainWindow', 'Refresh Devices'))
        
        if hasattr(self, 'history_btn'):
            self.history_btn.setText(QCoreApplication.translate('MainWindow', 'Device History'))
        
        if hasattr(self, 'search_btn'):
            self.search_btn.setText(QCoreApplication.translate('MainWindow', 'Search'))
        
        if hasattr(self, 'flash_btn'):
            self.flash_btn.setText(QCoreApplication.translate('MainWindow', 'Flash Firmware'))
        
        if hasattr(self, 'email_btn'):
            self.email_btn.setText(QCoreApplication.translate('MainWindow', 'Send Email'))
        
        if hasattr(self, 'settings_btn'):
            self.settings_btn.setText(QCoreApplication.translate('MainWindow', 'Settings'))

        if hasattr(self, 'open_stm32_btn'):
            self.open_stm32_btn.setText(QCoreApplication.translate('MainWindow', 'Open Project'))
        
        # Update settings buttons
        if hasattr(self, 'email_settings_btn'):
            self.email_settings_btn.setText(QCoreApplication.translate('Settings', 'Configure Email'))
        
        if hasattr(self, 'onedrive_settings_btn'):
            self.onedrive_settings_btn.setText(QCoreApplication.translate('Settings', 'OneDrive'))
        
        # Update device table headers
        if hasattr(self, 'device_table'):
            headers = [
                "",
                QCoreApplication.translate("MainWindow", "Port"),
                QCoreApplication.translate("MainWindow", "Type"),
                QCoreApplication.translate("MainWindow", "UID"),
                QCoreApplication.translate("MainWindow", "Firmware"),
                QCoreApplication.translate("MainWindow", "Status"),
                QCoreApplication.translate("MainWindow", "Last Seen"),
            ]
            self.device_table.setHorizontalHeaderLabels(headers)
        
        # Logs panel removed; no placeholder update

        # Update status bar message
        self._show_status(QCoreApplication.translate("MainWindow", "Ready"))

        # Language selector removed from status bar
        
        # Update status messages
        self.log(f"[{QCoreApplication.translate('Messages', 'Language Applied')}] {QCoreApplication.translate('Messages', 'Language Applied')}")
    
    def show_theme_language_dialog(self):
        """Show visual theme and language selection dialog."""
        dialog = ThemeLanguageSelectionDialog(self.theme_manager, self.translation_manager, self)
        if dialog.exec() == QDialog.Accepted:
            # Refresh all UI strings immediately after language/theme change
            self.update_ui_text()

            # Adjust layout direction for RTL languages
            if self.translation_manager.is_rtl_language():
                self.setLayoutDirection(Qt.RightToLeft)
            else:
                self.setLayoutDirection(Qt.LeftToRight)

            self.log(f"[{QCoreApplication.translate('Messages', 'Settings Applied')}] {QCoreApplication.translate('Messages', 'Theme and language settings have been applied successfully!')}")
            QMessageBox.information(self, QCoreApplication.translate("Dialogs", "Settings Applied"), 
                                   QCoreApplication.translate("Messages", "Theme and language settings have been applied successfully!"))

    def on_language_combo_changed(self, index: int):
        """Handle language selection from status bar combo box."""
        code = self.language_combo.itemData(index)
        if code:
            self.translation_manager.set_language(code)
            # UI update is triggered by translator via LanguageChange, but ensure immediate refresh
            self.update_ui_text()
            # Update layout direction as well
            if self.translation_manager.is_rtl_language():
                self.setLayoutDirection(Qt.RightToLeft)
            else:
                self.setLayoutDirection(Qt.LeftToRight)

            # Set QLocale default to match selected language for date/time formatting
            try:
                if code == "fr":
                    QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
                else:
                    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
            except Exception:
                pass

            # Refresh footer labels to reflect new locale
            try:
                self._update_footer_clock()
                if hasattr(self, 'footer_geo_label'):
                    self.footer_geo_label.setText(self._format_footer_geo())
            except Exception:
                pass

    def changeEvent(self, event):
        """React to Qt language change events by retranslating UI."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        """Re-apply all translations to visible UI elements."""
        self.update_ui_text()

        # Also refresh footer texts on language change
        try:
            self._update_footer_clock()
            if hasattr(self, 'footer_geo_label'):
                self.footer_geo_label.setText(self._format_footer_geo())
        except Exception:
            pass

    def _update_footer_clock(self):
        """Update the footer clock label with localized date/time and UTC offset."""
        try:
            # Localized date & time using QLocale
            now_qt = QDateTime.currentDateTime()
            localized_dt = QLocale().toString(now_qt, QLocale.ShortFormat)

            # UTC offset
            now_py = datetime.now().astimezone()
            offset = now_py.utcoffset() or timedelta(0)
            total_minutes = int(offset.total_seconds() // 60)
            sign = '+' if total_minutes >= 0 else '-'
            hh = abs(total_minutes) // 60
            mm = abs(total_minutes) % 60
            offset_str = f"UTC{sign}{hh:02d}:{mm:02d}"

            self.footer_clock_label.setText(f"🕒 {localized_dt} · {offset_str}")
        except Exception as e:
            logger.debug(f"Footer clock update failed: {e}")

    def _format_footer_geo(self) -> str:
        """Return formatted footer text for location and timezone."""
        try:
            tz = get_timezone()
            city, country = get_location()
            city = city or QCoreApplication.translate("Footer", "Unknown")
            country = country or QCoreApplication.translate("Footer", "Unknown")
            tz = tz or QCoreApplication.translate("Footer", "Unknown")
            return f"📍 {city}, {country} · 🌐 {tz}"
        except Exception as e:
            logger.debug(f"Footer geo format failed: {e}")
            return QCoreApplication.translate("Footer", "Location: Unknown")
    
    def show_device_history_dialog(self):
        """Show device history dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Device History")
        dialog.setWindowState(Qt.WindowMaximized)
        
        layout = QVBoxLayout()
        
        # Device history table
        history_table = QTableWidget()
        # Columns: Name, Type, UID, Port, Status, Last Seen, Connections, Machine ID
        history_table.setColumnCount(8)
        history_table.setHorizontalHeaderLabels([
            "Name", "Type", "UID", "Port", "Status", "Last Seen", "Connections", "Machine ID"
        ])
        
        # Populate history
        device_history = self.device_detector.get_device_history()
        history_table.setRowCount(len(device_history))
        
        for row, (device_id, device) in enumerate(device_history.items()):
            history_table.setItem(row, 0, QTableWidgetItem(device.get_display_name()))
            history_table.setItem(row, 1, QTableWidgetItem(device.board_type.value))
            history_table.setItem(row, 2, QTableWidgetItem(device.get_unique_id()))
            history_table.setItem(row, 3, QTableWidgetItem(device.port))
            history_table.setItem(row, 4, QTableWidgetItem(device.status))

            last_seen = device.last_seen.split('T')[0] if device.last_seen else "Never"
            history_table.setItem(row, 5, QTableWidgetItem(last_seen))
            history_table.setItem(row, 6, QTableWidgetItem(str(device.connection_count)))
            history_table.setItem(row, 7, QTableWidgetItem(self.machine_id.text() or "-"))
        
        history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(history_table)
        
        # Statistics
        stats = self.device_detector.get_device_statistics()
        stats_text = f"""
        <b>Device Statistics:</b><br>
        Total Devices: {stats['total_devices']}<br>
        Connected: {stats['connected_devices']}<br>
        Disconnected: {stats['disconnected_devices']}<br>
        Templates: {stats['templates_count']}
        """
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet("color: #333; font-size: 12px; background: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(stats_label)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        dialog.exec()

    def open_stm32_project_dialog(self):
        """Ask user for local project path or Git URL, then open STM32CubeIDE."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QRadioButton, QLineEdit, QHBoxLayout,
            QPushButton, QLabel, QFileDialog, QDialogButtonBox, QListWidget,
            QListWidgetItem, QProgressDialog, QWidget
        )
        from PySide6.QtCore import QProcess, QSettings, Qt
        from pathlib import Path
        import subprocess
        import shutil
        from src.core.ide_launcher import launch_stm32cubeide, stm32cubeide_install_status

        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate('MainWindow', 'Open Project'))
        dialog.setMinimumWidth(600)
        dialog.setObjectName("open_project_dialog")
        # Remove Maximize call to keep dialog compact
        # dialog.setWindowState(Qt.WindowMaximized)
        
        main_layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # IDE status
        ide_status_label = QLabel()
        ide_status_label.setWordWrap(True)
        installed, ide_path, source = stm32cubeide_install_status()
        if installed and ide_path:
            ide_status_label.setText(QCoreApplication.translate('MainWindow', f'STM32CubeIDE: Found at {ide_path} (via {source})'))
            ide_status_label.setStyleSheet('color: #2e7d32;')  # green
        else:
            ide_status_label.setText(QCoreApplication.translate(
                'MainWindow',
                'STM32CubeIDE: Not found. Install it or set env var STM32CUBEIDE_BIN to the exe path.'
            ))
            ide_status_label.setStyleSheet('color: #c62828;')  # red
        layout.addWidget(ide_status_label)

        # Mode selection
        mode_local = QRadioButton(QCoreApplication.translate('MainWindow', 'Use local project path'))
        mode_local.setObjectName("open_project_mode_local")
        mode_git = QRadioButton(QCoreApplication.translate('MainWindow', 'Clone from Git URL'))
        mode_git.setObjectName("open_project_mode_git")
        mode_local.setChecked(True)
        layout.addWidget(mode_local)
        layout.addWidget(mode_git)

        # Local path chooser (wrapped in a container for visibility toggle)
        from PySide6.QtWidgets import QWidget
        local_container = QWidget()
        local_container_row = QHBoxLayout()
        local_container.setLayout(local_container_row)
        local_container_row.addWidget(QLabel(QCoreApplication.translate('MainWindow', 'Project Folder:')))
        local_input = QLineEdit()
        local_input.setObjectName("open_local_input")
        local_input.setPlaceholderText(QCoreApplication.translate('MainWindow', 'Select a folder containing the project'))
        local_container_row.addWidget(local_input)
        browse_local = QPushButton(QCoreApplication.translate('MainWindow', 'Browse...'))
        def _browse_local():
            d = QFileDialog.getExistingDirectory(dialog, QCoreApplication.translate('MainWindow', 'Select Project Folder'))
            if d:
                local_input.setText(d)
        browse_local.clicked.connect(_browse_local)
        local_container_row.addWidget(browse_local)
        layout.addWidget(local_container)

        # Helper hint (shown for local mode)
        hint_label = QLabel()
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet('color: #616161; font-size: 12px;')
        layout.addWidget(hint_label)

        # Git URL (wrapped in a container for visibility toggle)
        git_url_container = QWidget()
        git_url_row = QHBoxLayout()
        git_url_container.setLayout(git_url_row)
        git_url_row.addWidget(QLabel(QCoreApplication.translate('MainWindow', 'Git URL:')))
        git_url_input = QLineEdit()
        git_url_input.setObjectName("open_git_input")
        git_url_input.setPlaceholderText('https://gitlab.com/owner/repo.git')
        git_url_row.addWidget(git_url_input)
        layout.addWidget(git_url_container)

        dest_container = QWidget()
        dest_row = QHBoxLayout()
        dest_container.setLayout(dest_row)
        dest_row.addWidget(QLabel(QCoreApplication.translate('MainWindow', 'Destination Folder:')))
        dest_input = QLineEdit()
        dest_input.setPlaceholderText(QCoreApplication.translate('MainWindow', 'Where to clone on your laptop'))
        dest_row.addWidget(dest_input)
        browse_dest = QPushButton(QCoreApplication.translate('MainWindow', 'Select'))
        def _browse_dest():
            d = QFileDialog.getExistingDirectory(dialog, QCoreApplication.translate('MainWindow', 'Select Destination Folder'))
            if d:
                dest_input.setText(d)
        browse_dest.clicked.connect(_browse_dest)
        dest_row.addWidget(browse_dest)
        layout.addWidget(dest_container)

        # Workspace selector (visible in both modes)
        workspace_container = QWidget()
        ws_row = QHBoxLayout()
        workspace_container.setLayout(ws_row)
        ws_row.addWidget(QLabel(QCoreApplication.translate('MainWindow', 'Workspace Folder:')))
        workspace_input = QLineEdit()
        workspace_input.setPlaceholderText(QCoreApplication.translate('MainWindow', 'Leave empty to use default workspace on same drive'))
        ws_row.addWidget(workspace_input)
        browse_ws = QPushButton(QCoreApplication.translate('MainWindow', 'Select'))
        def _browse_ws():
            d = QFileDialog.getExistingDirectory(dialog, QCoreApplication.translate('MainWindow', 'Select Workspace Folder'))
            if d:
                workspace_input.setText(d)
        browse_ws.clicked.connect(_browse_ws)
        ws_row.addWidget(browse_ws)
        layout.addWidget(workspace_container)

        # Add stretch to push content up
        layout.addStretch()

        # Visibility toggle based on mode selection
        def _update_mode():
            if mode_local.isChecked():
                local_container.setVisible(True)
                hint_label.setVisible(True)
                git_url_container.setVisible(False)
                dest_container.setVisible(False)
                hint_label.setText(QCoreApplication.translate(
                    'MainWindow',
                    'Tip: If the selected folder lacks a .project file, I will auto-search up to two subfolders and import the first CubeIDE project found. You can also import manually in CubeIDE via File → Import → Existing Projects into Workspace.'
                ))
            else:
                local_container.setVisible(False)
                hint_label.setVisible(True)
                git_url_container.setVisible(True)
                dest_container.setVisible(True)
                hint_label.setText(QCoreApplication.translate(
                    'MainWindow',
                    'After cloning, I will try to auto-import the project into the workspace using the same detection logic.'
                ))

        mode_local.toggled.connect(_update_mode)
        mode_git.toggled.connect(_update_mode)
        _update_mode()

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        ok_btn.setEnabled(False)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        main_layout.addWidget(buttons)

        # Helper: simple validation for enabling OK
        def _is_valid_git_url(u: str) -> bool:
            return u.startswith('https://') or u.startswith('ssh://') or u.startswith('git@')

        def _update_ok_enabled():
            if mode_local.isChecked():
                ok_btn.setEnabled(bool(local_input.text().strip()))
            else:
                ok_btn.setEnabled(bool(git_url_input.text().strip()) and bool(dest_input.text().strip()) and _is_valid_git_url(git_url_input.text().strip()))

        # Wire validation updates
        local_input.textChanged.connect(_update_ok_enabled)
        git_url_input.textChanged.connect(_update_ok_enabled)
        dest_input.textChanged.connect(_update_ok_enabled)
        mode_local.toggled.connect(_update_ok_enabled)
        mode_git.toggled.connect(_update_ok_enabled)
        _update_ok_enabled()

        # Persist/restore last-used inputs via QSettings
        settings = QSettings('AWG', 'AWG Kumulus Device Manager')
        last_mode = settings.value('open_project/mode', 'local')
        last_local = settings.value('open_project/local_path', '')
        last_git = settings.value('open_project/git_url', '')
        last_dest = settings.value('open_project/dest_path', '')
        last_ws = settings.value('open_project/workspace_path', '')
        if last_mode == 'git':
            mode_git.setChecked(True)
        else:
            mode_local.setChecked(True)
        local_input.setText(last_local)
        git_url_input.setText(last_git)
        dest_input.setText(last_dest)
        workspace_input.setText(last_ws)

        # Helper: scan for sub-projects containing .project up to depth 2
        def _scan_subprojects(base: Path) -> list[Path]:
            results: list[Path] = []
            try:
                max_dirs = 4000
                seen = 0
                for dirpath, dirnames, filenames in os.walk(base):
                    try:
                        rel = Path(dirpath).relative_to(base)
                        depth = len(rel.parts)
                    except Exception:
                        depth = 0
                    if depth > 2:
                        dirnames[:] = []
                        continue
                    if '.project' in filenames:
                        results.append(Path(dirpath))
                    seen += 1
                    if seen >= max_dirs:
                        break
            except Exception:
                pass
            return results

        # Helper: choose subproject when multiple found
        def _choose_subproject(paths: list[Path]) -> Optional[Path]:
            chooser = QDialog(dialog)
            chooser.setWindowTitle(QCoreApplication.translate('MainWindow', 'Select Sub-Project'))
            chooser.setMinimumWidth(560)
            v = QVBoxLayout()
            v.addWidget(QLabel(QCoreApplication.translate('MainWindow', 'Multiple CubeIDE projects were detected. Please select one:')))
            lw = QListWidget()
            for p in paths:
                item = QListWidgetItem(str(p))
                lw.addItem(item)
            v.addWidget(lw)
            bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            v.addWidget(bb)
            chooser.setLayout(v)
            chosen: Optional[Path] = None
            def _ok():
                nonlocal chosen
                it = lw.currentItem()
                if it:
                    chosen = Path(it.text())
                    chooser.accept()
            bb.accepted.connect(_ok)
            bb.rejected.connect(chooser.reject)
            chooser.exec()
            return chosen

        def _on_accept():
            try:
                if mode_local.isChecked():
                    proj = local_input.text().strip()
                    if not proj:
                        QMessageBox.warning(dialog, QCoreApplication.translate('Dialogs', 'Validation Error'), QCoreApplication.translate('Messages', 'Please select a project folder'))
                        return
                    p = Path(proj)
                    if not p.exists():
                        QMessageBox.warning(dialog, QCoreApplication.translate('Dialogs', 'Not Found'), QCoreApplication.translate('Messages', 'Selected folder does not exist'))
                        return
                    # If folder already contains one or more CubeIDE projects, confirm with user
                    existing_subprojects = _scan_subprojects(p)
                    if existing_subprojects:
                        confirm = QMessageBox(dialog)
                        confirm.setIcon(QMessageBox.Warning)
                        confirm.setWindowTitle(QCoreApplication.translate('MainWindow', 'Confirm Project Folder'))
                        confirm.setText(QCoreApplication.translate(
                            'MainWindow',
                            'The selected folder already contains a CubeIDE project. Do you want to open this folder, or choose another?'
                        ))
                        use_btn = confirm.addButton(QCoreApplication.translate('MainWindow', 'Use This Folder'), QMessageBox.YesRole)
                        choose_btn = confirm.addButton(QCoreApplication.translate('MainWindow', 'Choose Another'), QMessageBox.NoRole)
                        confirm.exec()
                        if confirm.clickedButton() == choose_btn:
                            d = QFileDialog.getExistingDirectory(dialog, QCoreApplication.translate('MainWindow', 'Select Project Folder'))
                            if d:
                                local_input.setText(d)
                            return  # Let user re-try with the new folder
                    # If multiple sub-projects found, let user choose
                    subprojects = _scan_subprojects(p)
                    chosen_dir = p
                    if len(subprojects) > 1:
                        pick = _choose_subproject(subprojects)
                        if pick:
                            chosen_dir = pick
                    ws_text = workspace_input.text().strip()
                    ws_path = Path(ws_text) if ws_text else None

                    # Show loading dialog
                    loading = QProgressDialog(QCoreApplication.translate('MainWindow', 'Launching STM32CubeIDE...'), None, 0, 0, dialog)
                    loading.setWindowTitle(QCoreApplication.translate('MainWindow', 'Please Wait'))
                    loading.setWindowModality(Qt.WindowModal)
                    loading.setMinimumDuration(0)
                    loading.show()
                    QCoreApplication.processEvents()

                    try:
                        ok, msg = launch_stm32cubeide(chosen_dir, ws_path)
                    finally:
                        loading.close()
                    self.log(f"[{QCoreApplication.translate('MainWindow', 'Open Project')}] {msg}")
                    if not ok:
                        QMessageBox.warning(dialog, QCoreApplication.translate('Dialogs', 'Error'), msg)
                    dialog.accept()
                else:
                    url = git_url_input.text().strip()
                    dest = dest_input.text().strip()
                    if not url or not dest:
                        QMessageBox.warning(dialog, QCoreApplication.translate('Dialogs', 'Validation Error'), QCoreApplication.translate('Messages', 'Please provide both Git URL and destination'))
                        return
                    if not shutil.which('git'):
                        QMessageBox.warning(dialog, QCoreApplication.translate('Dialogs', 'Git Not Found'), QCoreApplication.translate('Messages', 'Please install Git and ensure it is in PATH'))
                        return
                    # Pre-clone check: if destination exists and contains a CubeIDE project (or any files), confirm with user
                    dest_path = Path(dest)
                    pre_existing_projects = _scan_subprojects(dest_path) if dest_path.exists() else []
                    dest_has_files = False
                    try:
                        dest_has_files = dest_path.exists() and any(dest_path.iterdir())
                    except Exception:
                        dest_has_files = False
                    if pre_existing_projects or dest_has_files:
                        confirm = QMessageBox(dialog)
                        confirm.setIcon(QMessageBox.Warning)
                        confirm.setWindowTitle(QCoreApplication.translate('MainWindow', 'Confirm Destination'))
                        confirm.setText(QCoreApplication.translate(
                            'MainWindow',
                            'The destination folder already contains files or a CubeIDE project. Do you want to use this folder for the new clone, or choose another?'
                        ))
                        use_btn = confirm.addButton(QCoreApplication.translate('MainWindow', 'Use This Folder'), QMessageBox.YesRole)
                        choose_btn = confirm.addButton(QCoreApplication.translate('MainWindow', 'Choose Another'), QMessageBox.NoRole)
                        confirm.exec()
                        if confirm.clickedButton() == choose_btn:
                            d = QFileDialog.getExistingDirectory(dialog, QCoreApplication.translate('MainWindow', 'Select Destination Folder'))
                            if d:
                                dest_input.setText(d)
                            return  # Let user re-try with the new destination
                    # Use QProcess to stream clone output and allow cancel
                    progress = QDialog(dialog)
                    progress.setWindowTitle(QCoreApplication.translate('MainWindow', 'Cloning Repository'))
                    pv = QVBoxLayout()
                    log_label = QLabel(QCoreApplication.translate('MainWindow', 'Running: git clone'))
                    pv.addWidget(log_label)
                    # Progress bar for clone percent
                    progress_bar = QProgressBar()
                    progress_bar.setRange(0, 100)
                    progress_bar.setValue(0)
                    pv.addWidget(progress_bar)
                    # Live log view
                    log_text = QTextEdit()
                    log_text.setReadOnly(True)
                    pv.addWidget(log_text)
                    pb = QDialogButtonBox(QDialogButtonBox.Cancel)
                    pv.addWidget(pb)
                    progress.setLayout(pv)
                    proc = QProcess(progress)
                    proc.setProgram('git')
                    # Request progress output and parse stderr lines such as
                    # "Receiving objects:  12%" to drive the progress bar
                    proc.setArguments(['clone', '--progress', url, dest])
                    proc.setProcessChannelMode(QProcess.SeparateChannels)
                    def _on_out():
                        data = bytes(proc.readAllStandardOutput()).decode(errors='ignore')
                        log_text.append(data)
                    def _on_err():
                        data = bytes(proc.readAllStandardError()).decode(errors='ignore')
                        log_text.append(data)
                        # Try to extract percentage from progress lines
                        m = re.search(r"(\d+)%", data)
                        if m:
                            try:
                                progress_bar.setValue(int(m.group(1)))
                            except Exception:
                                pass
                    def _on_finished(code, status):
                        progress.accept()
                    proc.readyReadStandardOutput.connect(_on_out)
                    proc.readyReadStandardError.connect(_on_err)
                    proc.finished.connect(_on_finished)
                    pb.rejected.connect(lambda: (proc.kill(), progress.reject()))
                    proc.start()
                    progress.exec()
                    if proc.exitStatus() != QProcess.NormalExit or proc.exitCode() != 0:
                        QMessageBox.critical(dialog, QCoreApplication.translate('Dialogs', 'Clone Failed'), QCoreApplication.translate('Messages', 'Git clone failed or was cancelled'))
                        return
                    self.log(QCoreApplication.translate('Messages', 'Repository cloned successfully'))
                    # After clone, scan for subprojects and choose if multiple
                    dest_path = Path(dest_input.text().strip()) if dest_input.text().strip() else Path(dest)
                    subprojects = _scan_subprojects(dest_path)
                    chosen_dir = dest_path
                    if len(subprojects) > 1:
                        pick = _choose_subproject(subprojects)
                        if pick:
                            chosen_dir = pick
                    ws_text = workspace_input.text().strip()
                    ws_path = Path(ws_text) if ws_text else None

                    # Show loading dialog
                    loading = QProgressDialog(QCoreApplication.translate('MainWindow', 'Launching STM32CubeIDE...'), None, 0, 0, dialog)
                    loading.setWindowTitle(QCoreApplication.translate('MainWindow', 'Please Wait'))
                    loading.setWindowModality(Qt.WindowModal)
                    loading.setMinimumDuration(0)
                    loading.show()
                    QCoreApplication.processEvents()

                    try:
                        ok, msg = launch_stm32cubeide(chosen_dir, ws_path)
                    finally:
                        loading.close()
                    self.log(f"[{QCoreApplication.translate('MainWindow', 'Open Project')}] {msg}")
                    if not ok:
                        QMessageBox.warning(dialog, QCoreApplication.translate('Dialogs', 'Error'), msg)
                    dialog.accept()
            except Exception as e:
                QMessageBox.critical(dialog, QCoreApplication.translate('Dialogs', 'Error'), str(e))

        buttons.accepted.connect(_on_accept)
        buttons.rejected.connect(dialog.reject)
        # Persist on close
        def _persist():
            settings.setValue('open_project/mode', 'git' if mode_git.isChecked() else 'local')
            settings.setValue('open_project/local_path', local_input.text().strip())
            settings.setValue('open_project/git_url', git_url_input.text().strip())
            settings.setValue('open_project/dest_path', dest_input.text().strip())
            settings.setValue('open_project/workspace_path', workspace_input.text().strip())
        dialog.finished.connect(lambda _: _persist())
        dialog.exec()
    
    def show_device_templates_dialog(self):
        """Show device templates dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Device Templates")
        dialog.setWindowState(Qt.WindowMaximized)
        
        layout = QVBoxLayout()
        
        # Templates list
        templates_list = QListWidget()
        templates = self.device_detector.get_device_templates()
        
        for template_name, template_data in templates.items():
            item_text = f"{template_name} - {template_data.get('description', 'No description')}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, template_name)
            templates_list.addItem(item)
        
        layout.addWidget(templates_list)
        
        # Template buttons
        template_buttons = QHBoxLayout()
        
        create_btn = QPushButton("Create from Current")
        create_btn.clicked.connect(lambda: self.create_template_from_current(dialog))
        template_buttons.addWidget(create_btn)
        
        apply_btn = QPushButton("Apply Template")
        apply_btn.clicked.connect(lambda: self.apply_template(dialog, templates_list))
        template_buttons.addWidget(apply_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_template(dialog, templates_list))
        template_buttons.addWidget(delete_btn)
        
        layout.addLayout(template_buttons)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def show_device_search_dialog(self):
        """Show device search dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Search Devices")
        dialog.setWindowState(Qt.WindowMaximized)
        
        layout = QVBoxLayout()

        # Search input
        search_layout = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Enter search query...")
        search_layout.addWidget(search_input)

        search_btn = QPushButton("Search")
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)

        # Search results
        results_table = QTableWidget()
        results_table.setColumnCount(6)
        results_table.setHorizontalHeaderLabels([
            "Name", "Type", "Port", "Status", "Health", "Tags"
        ])
        layout.addWidget(results_table)

        def perform_search():
            query = search_input.text().strip()
            if not query:
                return

            results = self.device_detector.search_devices(query)
            results_table.setRowCount(len(results))

            for row, device in enumerate(results):
                results_table.setItem(row, 0, QTableWidgetItem(device.get_display_name()))
                results_table.setItem(row, 1, QTableWidgetItem(device.board_type.value))
                results_table.setItem(row, 2, QTableWidgetItem(device.port))
                results_table.setItem(row, 3, QTableWidgetItem(device.status))

                health_score = self.device_detector.get_device_health_score(device)
                health_item = QTableWidgetItem(f"{health_score}%")
                if health_score >= 80:
                    health_item.setBackground(Qt.green)
                elif health_score >= 60:
                    health_item.setBackground(Qt.yellow)
                else:
                    health_item.setBackground(Qt.red)
                results_table.setItem(row, 4, health_item)

                tags = ", ".join(device.tags) if device.tags else "None"
                results_table.setItem(row, 5, QTableWidgetItem(tags))

            results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        search_btn.clicked.connect(perform_search)
        search_input.returnPressed.connect(perform_search)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        dialog.exec()
    
    def create_template_from_current(self, dialog):
        """Create a template from currently selected device."""
        if not self.devices:
            QMessageBox.warning(dialog, "No Devices", "No devices currently connected")
            return
        
        # Simple template creation dialog
        name, ok = QInputDialog.getText(dialog, "Create Template", "Template name:")
        if not ok or not name.strip():
            return
        
        description, ok = QInputDialog.getText(dialog, "Create Template", "Description:")
        if not ok:
            description = ""
        
        # Use first connected device
        device = self.devices[0]
        self.device_detector.create_device_template(name.strip(), device, description)
        
        QMessageBox.information(dialog, "Success", f"Template '{name}' created successfully!")
        dialog.accept()  # Close and reopen to refresh
    
    def apply_template(self, dialog, templates_list):
        """Apply selected template."""
        current_item = templates_list.currentItem()
        if not current_item:
            QMessageBox.warning(dialog, "No Selection", "Please select a template")
            return
        
        template_name = current_item.data(Qt.UserRole)
        if not self.devices:
            QMessageBox.warning(dialog, "No Devices", "No devices currently connected")
            return
        
        # Apply template to first connected device
        device = self.devices[0]
        template_device = self.device_detector.apply_device_template(template_name, device.port)
        
        if template_device:
            QMessageBox.information(dialog, "Success", f"Template '{template_name}' applied successfully!")
            self.refresh_devices()
        else:
            QMessageBox.warning(dialog, "Error", "Failed to apply template")
    
    def show_device_context_menu(self, position):
        """Show context menu with clear copy actions and customization options."""
        item = self.device_table.itemAt(position)
        if not item:
            return
        row = item.row()
        if row >= len(self.devices):
            return
        device = self.devices[row]

        menu = QMenu(self)
        # Copy actions
        copy_cell = menu.addAction(QCoreApplication.translate("MainWindow", "Copy Cell Value"))
        copy_cell.triggered.connect(lambda: self._copy_text(item.text()))
        copy_row = menu.addAction(QCoreApplication.translate("MainWindow", "Copy Row (CSV)"))
        def _row_csv(r):
            vals = [self.device_table.item(r, c).text() if self.device_table.item(r, c) else "" for c in range(self.device_table.columnCount())]
            return ",".join(vals)
        copy_row.triggered.connect(lambda: self._copy_text(_row_csv(row)))
        menu.addSeparator()

        # Existing actions
        customize_action = menu.addAction(QCoreApplication.translate("MainWindow", "Customize Device"))
        customize_action.triggered.connect(lambda: self.customize_device_dialog(device))
        backups_action = menu.addAction(QCoreApplication.translate("MainWindow", "View Firmware Backups"))
        backups_action.triggered.connect(lambda: self.show_firmware_backups_dialog(device))

        menu.exec(self.device_table.viewport().mapToGlobal(position))
    
    def customize_device_dialog(self, device: Device):
        """Open dialog to customize device (name, notes)."""
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Customize Device"))
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # Device info
        info_label = QLabel(f"<b>{QCoreApplication.translate('MainWindow', 'Device:')}</b> {device.port} ({device.board_type.value})")
        layout.addWidget(info_label)
        
        # Custom name
        name_label = QLabel(QCoreApplication.translate("MainWindow", "Custom Name:"))
        layout.addWidget(name_label)
        name_input = QLineEdit()
        name_input.setText(device.custom_name or "")
        name_input.setPlaceholderText(QCoreApplication.translate("MainWindow", "Enter a custom name for this device"))
        layout.addWidget(name_input)
        
        # Notes
        notes_label = QLabel(QCoreApplication.translate("MainWindow", "Notes:"))
        layout.addWidget(notes_label)
        notes_input = QTextEdit()
        notes_input.setPlainText(device.notes or "")
        notes_input.setPlaceholderText(QCoreApplication.translate("MainWindow", "Add notes about this device"))
        notes_input.setMaximumHeight(150)
        layout.addWidget(notes_input)
        
        # Health score display
        health_score = self.device_detector.get_device_health_score(device)
        health_label = QLabel(f"<b>{QCoreApplication.translate('MainWindow', 'Health Score:')}</b> {health_score}%")
        if health_score >= 80:
            health_label.setStyleSheet("color: green;")
        elif health_score >= 60:
            health_label.setStyleSheet("color: orange;")
        else:
            health_label.setStyleSheet("color: red;")
        layout.addWidget(health_label)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.Accepted:
            # Update device
            device.custom_name = name_input.text().strip() if name_input.text().strip() else None
            device.notes = notes_input.toPlainText().strip() if notes_input.toPlainText().strip() else None
            
            # Update health score
            device.health_score = self.device_detector.get_device_health_score(device)
            
            # Save to history
            self.device_detector.update_device_in_history(device)
            
            # Refresh table
            self.update_device_table()
            
            QMessageBox.information(self, "Success", QCoreApplication.translate("MainWindow", "Device customized successfully!"))
    
    def show_firmware_backups_dialog(self, device: Device):
        """Show dialog to view and manage firmware backups for a device."""
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Firmware Backups"))
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        
        # Device info
        info_label = QLabel(f"<b>{QCoreApplication.translate('MainWindow', 'Device:')}</b> {device.get_display_name()} ({device.port})")
        layout.addWidget(info_label)
        
        # Get backups
        backups = self.firmware_flasher.firmware_manager.get_device_backups(device)
        
        if not backups:
            no_backups_label = QLabel(QCoreApplication.translate("MainWindow", "No firmware backups available for this device."))
            no_backups_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(no_backups_label)
        else:
            # Backups table
            backups_table = QTableWidget()
            backups_table.setColumnCount(5)
            backups_table.setHorizontalHeaderLabels([
                QCoreApplication.translate("MainWindow", "Date"),
                QCoreApplication.translate("MainWindow", "Version"),
                QCoreApplication.translate("MainWindow", "Reason"),
                QCoreApplication.translate("MainWindow", "Size"),
                QCoreApplication.translate("MainWindow", "Actions")
            ])
            backups_table.setRowCount(len(backups))
            
            for row, backup in enumerate(backups):
                # Date
                backup_date = backup.backup_date.split('T')[0] if backup.backup_date else "Unknown"
                backups_table.setItem(row, 0, QTableWidgetItem(backup_date))
                
                # Version
                version = backup.firmware_info.version if backup.firmware_info else "Unknown"
                backups_table.setItem(row, 1, QTableWidgetItem(version))
                
                # Reason
                reason = backup.reason.replace('_', ' ').title()
                backups_table.setItem(row, 2, QTableWidgetItem(reason))
                
                # Size
                size = backup.firmware_info.size if backup.firmware_info else 0
                size_str = f"{size / 1024:.1f} KB" if size else "Unknown"
                backups_table.setItem(row, 3, QTableWidgetItem(size_str))
                
                # Actions
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(2, 2, 2, 2)
                
                rollback_btn = QPushButton(QCoreApplication.translate("MainWindow", "Rollback"))
                rollback_btn.clicked.connect(lambda checked, b=backup, idx=row: self._rollback_from_backup_dialog(device, b, idx))
                action_layout.addWidget(rollback_btn)
                
                delete_btn = QPushButton(QCoreApplication.translate("MainWindow", "Delete"))
                delete_btn.clicked.connect(lambda checked, b=backup, idx=row: self._delete_backup(device, b, idx, backups_table))
                action_layout.addWidget(delete_btn)
                
                backups_table.setCellWidget(row, 4, action_widget)
            
            backups_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(backups_table)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def _rollback_from_backup_dialog(self, device: Device, backup, backup_index: int):
        """Rollback firmware from backup."""
        reply = QMessageBox.question(
            self,
            QCoreApplication.translate("MainWindow", "Confirm Rollback"),
            QCoreApplication.translate("MainWindow", "Are you sure you want to rollback to this firmware version?\n\nA backup of the current firmware will be created first."),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                def progress_callback(message):
                    self.log(message)
                
                success = self.firmware_flasher.rollback_firmware(device, backup_index, progress_callback)
                
                if success:
                    QMessageBox.information(self, "Success", QCoreApplication.translate("MainWindow", "Firmware rollback completed successfully!"))
                    self.refresh_devices()
                else:
                    QMessageBox.warning(self, "Failed", QCoreApplication.translate("MainWindow", "Firmware rollback failed!"))
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"{QCoreApplication.translate('MainWindow', 'Rollback error:')} {str(e)}")
                logger.error(f"Rollback error: {e}")
    
    def _delete_backup(self, device: Device, backup, backup_index: int, table: QTableWidget):
        """Delete a firmware backup."""
        reply = QMessageBox.question(
            self,
            QCoreApplication.translate("MainWindow", "Confirm Delete"),
            QCoreApplication.translate("MainWindow", "Are you sure you want to delete this backup?\n\nThis action cannot be undone."),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                device_id = device.get_unique_id()
                backups = self.firmware_flasher.firmware_manager.firmware_backups.get(device_id, [])
                
                if backup_index < len(backups):
                    # Delete backup file if exists
                    backup_path = Path(backups[backup_index].backup_path)
                    if backup_path.exists():
                        backup_path.unlink()
                    
                    # Remove from list
                    backups.pop(backup_index)
                    self.firmware_flasher.firmware_manager.firmware_backups[device_id] = backups
                    self.firmware_flasher.firmware_manager._save_firmware_backups()
                    
                    # Refresh table
                    self.show_firmware_backups_dialog(device)
                    
                    QMessageBox.information(self, "Success", QCoreApplication.translate("MainWindow", "Backup deleted successfully!"))
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"{QCoreApplication.translate('MainWindow', 'Delete error:')} {str(e)}")
                logger.error(f"Delete backup error: {e}")
    
    def delete_template(self, dialog, templates_list):
        """Delete selected template."""
        current_item = templates_list.currentItem()
        if not current_item:
            QMessageBox.warning(dialog, "No Selection", "Please select a template")
            return
        
        template_name = current_item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            dialog, "Confirm Delete", 
            f"Are you sure you want to delete template '{template_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.device_detector.delete_device_template(template_name)
            QMessageBox.information(dialog, "Success", f"Template '{template_name}' deleted successfully!")
            dialog.accept()  # Close and reopen to refresh

    def _run_auto_flash_worker(self, device, firmware_path=None, show_info_dialog=False):
        """Run auto-flash in a worker thread to prevent recursive repaints."""
        loading_dialog = self._show_uid_loading_overlay() if device.board_type.value == 'STM32' else None
        machine_id = self.machine_id.text() or ""
        
        def update_progress(msg):
            self._show_status(msg)
            if loading_dialog:
                loading_dialog.setLabelText(msg)
        
        # Connect to flasher signal
        self.firmware_flasher.progress_update.connect(update_progress)
        
        def task(device_obj, fw_path, mid):
            if hasattr(self.device_detector, 'pause_monitoring'):
                self.device_detector.pause_monitoring()
            try:
                def progress_emitter(msg):
                    self.firmware_flasher.progress_update.emit(msg)

                if not fw_path:
                    fw_path = self._ensure_uid_firmware_ready(progress_emitter)

                # Flash
                ok = self.firmware_flasher.flash_firmware(device_obj, str(fw_path))
                if not ok:
                    raise Exception("Flashing failed")
                
                # Read Info
                time.sleep(2.0)
                self.device_detector._read_device_info(device_obj)
                
                # Update info
                device_obj.extra_info = device_obj.extra_info or {}
                device_obj.extra_info["uid_flashed"] = True
                device_obj.extra_info["machine_id"] = mid
                
            finally:
                if hasattr(self.device_detector, 'resume_monitoring'):
                    self.device_detector.resume_monitoring()

        def cleanup():
            try:
                self.firmware_flasher.progress_update.disconnect(update_progress)
            except Exception:
                pass
            if loading_dialog:
                loading_dialog.close()

        def on_success():
            cleanup()
            self._show_status("Auto-flash: success")
            self.device_detector.update_device_in_history(device)
            self.refresh_devices()
            self._update_device_details(device)
            if show_info_dialog:
                try:
                    self._show_uid_info_dialog(device)
                except Exception:
                    pass

        def on_error(err_msg):
            cleanup()
            if "Internet connection required" in err_msg:
                 QMessageBox.warning(self, "Internet Required", err_msg)
            self._show_status(f"Auto-flash failed: {err_msg}")
            logger.warning(f"Auto-flash failed: {err_msg}")

        self.flash_worker = WorkerThread(task, device, firmware_path, machine_id)
        self.flash_worker.succeeded.connect(on_success)
        self.flash_worker.error.connect(on_error)
        self.flash_worker.start()

    def _auto_flash_on_connect(self, device: Device):
        cfg = self.config.get('auto_flash', {})
        path = cfg.get('firmware_path', '').strip()
        allowed = set(cfg.get('board_types', []) or [])
        enabled = bool(cfg.get('enabled', False))
        
        if allowed and device.board_type.value not in allowed:
            return

        if enabled and path:
            p = Path(path)
            if not p.exists():
                logger.warning(f"Auto-flash firmware path not found: {path}")
                return
            self._run_auto_flash_worker(device, str(p), show_info_dialog=True)
        else:
            # Default to UID firmware if it's STM32
            if device.board_type.value == 'STM32':
                self._run_auto_flash_worker(device, None, show_info_dialog=True)



    def _auto_flash_on_selection(self, device: Device):
        try:
            if not device or (device.status or '').lower() != 'connected':
                return
            # Avoid repeated flashing in one session
            if getattr(device, 'extra_info', None) and device.extra_info.get('uid_flashed'):
                return
            
            # Find row
            devices = getattr(self, 'filtered_devices', self.devices)
            try:
                row = devices.index(device)
            except ValueError:
                return
            
            # Trigger load (no info dialog)
            self._load_device_uid(device, row, show_info=False)
            
        except Exception as e:
            logger.warning(f"Selection auto-flash error: {e}")
    
    def _update_device_table_row(self, device: Device, row: int):
        """Update a specific row in the device table with new device info."""
        try:
            # Update UID column (3)
            uid_val = device.uid
            if not uid_val:
                uid_val = "—"
            it = QTableWidgetItem(uid_val)
            it.setToolTip(self._device_details_text(device))
            self.device_table.setItem(row, 3, it)

            # Update firmware (4)
            fw = getattr(device, 'firmware_version', None) or "-"
            self.device_table.setItem(row, 4, QTableWidgetItem(fw))

            # Update status (5)
            status_item = QTableWidgetItem(device.status)
            status_item.setToolTip(QCoreApplication.translate("MainWindow", "Click to copy. Right-click for options."))
            self.device_table.setItem(row, 5, status_item)

            # Update type (2)
            board_type = device.board_type.value
            it = QTableWidgetItem(board_type)
            it.setToolTip(QCoreApplication.translate("MainWindow", "Click to copy. Right-click for options."))
            self.device_table.setItem(row, 2, it)

        except Exception as e:
            logger.warning(f"Failed to update device table row: {e}")

    def _show_uid_info_dialog(self, device: Device):
        d = QDialog(self)
        d.setWindowTitle("Device UID & Info")
        d.resize(500, 600)  # Make it larger to fit the logs
        
        main_layout = QVBoxLayout()
        
        # --- Info Form ---
        form_group = QGroupBox("Device Details")
        form_layout = QFormLayout()

        # UID with read button for STM32
        uid_layout = QHBoxLayout()
        uid_label = QLabel(device.uid or "N/A")
        uid_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        uid_layout.addWidget(uid_label)
        form_layout.addRow(QLabel("UID:"), uid_layout)

        form_layout.addRow(QLabel("Chip ID:"), QLabel(device.chip_id or "N/A"))
        form_layout.addRow(QLabel("MAC:"), QLabel(device.mac_address or "N/A"))
        form_layout.addRow(QLabel("Firmware:"), QLabel(device.firmware_version or "N/A"))
        form_layout.addRow(QLabel("Hardware:"), QLabel(device.hardware_version or "N/A"))
        form_layout.addRow(QLabel("Flash:"), QLabel(device.flash_size or "N/A"))
        form_layout.addRow(QLabel("CPU:"), QLabel(device.cpu_frequency or "N/A"))
        form_layout.addRow(QLabel("Serial:"), QLabel(device.serial_number or "N/A"))
        form_layout.addRow(QLabel("Manufacturer:"), QLabel(device.manufacturer or "N/A"))
        
        def _fmt_hex(val):
            try:
                if val is None:
                    return None
                if isinstance(val, int):
                    return f"0x{val:04X}"
                s = str(val).strip()
                if s.lower().startswith("0x"):
                    return f"0x{int(s,16):04X}"
                return f"0x{int(s):04X}"
            except Exception:
                return str(val)
                
        form_layout.addRow(QLabel("VID:PID:"), QLabel(f"{_fmt_hex(device.vid)}:{_fmt_hex(device.pid)}" if device.vid and device.pid else "N/A"))
        form_group.setLayout(form_layout)
        main_layout.addWidget(form_group)
        
        # --- Serial Output Section ---
        if device.extra_info and 'serial_output' in device.extra_info:
            log_group = QGroupBox("Raw Serial Output")
            log_layout = QVBoxLayout()
            
            log_text = QTextEdit()
            log_text.setReadOnly(True)
            log_text.setPlainText(device.extra_info['serial_output'])
            log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 10px;")
            
            log_layout.addWidget(log_text)
            log_group.setLayout(log_layout)
            main_layout.addWidget(log_group)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(d.reject)
        main_layout.addWidget(btns)
        
        d.setLayout(main_layout)
        d.exec()

class ChipDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        col = index.column()
        text = str(index.data()) if index.data() is not None else ""
        # Check for Status column (5)
        if col == 5 and text:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            rect = option.rect.adjusted(6, 6, -6, -6)
            pal = option.palette
            bg = pal.alternateBase().color()
            fg = pal.windowText().color()
            
            # Status column logic
            t = text.lower()
            if "connected" in t:
                bg = pal.highlight().color().lighter(160)
            elif "disconnected" in t:
                bg = pal.brightText().color()
                bg = QColor(bg.red(), max(0, bg.green()-120), max(0, bg.blue()-120)).lighter(140)
            else:
                bg = pal.highlight().color().lighter(200)

            painter.setBrush(bg)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 10, 10)
            painter.setPen(fg)
            painter.drawText(rect, Qt.AlignCenter, text)
            painter.restore()
        else:
            super().paint(painter, option, index)
