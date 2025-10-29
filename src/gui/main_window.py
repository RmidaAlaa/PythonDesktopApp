"""Main application window."""

import sys
from typing import Dict
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QProgressBar, QMessageBox,
    QGroupBox, QSplitter, QApplication, QHeaderView, QDialog,
    QDialogButtonBox, QCheckBox, QFileDialog, QListWidget, QListWidgetItem,
    QSpinBox, QTabWidget, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QFont

from ..core.config import Config
from ..core.device_detector import DeviceDetector, Device
from ..core.report_generator import ReportGenerator
from ..core.email_sender import EmailSender
from ..core.firmware_flasher import FirmwareFlasher
from ..core.bootstrap import BootstrapManager
from ..core.logger import setup_logger
from ..core.language_manager import LanguageManager, LanguageType
from ..gui.theme_language_dialog import ThemeLanguageSelectionDialog
from ..core.onedrive_manager import OneDriveManager

logger = setup_logger("MainWindow")


class WorkerThread(QThread):
    """Worker thread for background operations."""
    finished = Signal()
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
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.config = Config.load_config()
        self.devices = []
        self.device_history = []
        self.last_report_path = None  # Store last generated report path
        self.setup_ui()
        
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        self.theme_manager.theme_changed.connect(self.on_theme_changed)
        
        # Initialize language manager
        self.language_manager = LanguageManager()
        self.language_manager.language_changed.connect(self.on_language_changed)
        
        # Initialize components
        self.device_detector = DeviceDetector()
        self.report_generator = ReportGenerator()
        self.email_sender = EmailSender()
        self.firmware_flasher = FirmwareFlasher()
        self.onedrive_manager = OneDriveManager()
        
        # Auto-detect devices on startup
        QTimer.singleShot(500, self.refresh_devices)
        
        # Start real-time monitoring with Qt signal handling
        self.device_detector.start_real_time_monitoring(self._device_change_callback)
        
        # Check for first run
        if Config.is_first_run():
            self.show_first_run_dialog()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("AWG Kumulus Device Manager v1.0.0")
        self.setMinimumSize(1200, 800)
        
        # Center window on screen
        self.center_window()
        
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Device list
        left_panel = self.create_device_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Controls
        right_panel = self.create_control_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([400, 800])
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def create_device_panel(self):
        """Create the device list panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("Connected Devices")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)
        
        # Device table
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(8)
        self.device_table.setHorizontalHeaderLabels([
            "Port", "Type", "VID:PID", "Status", "Health", "Name", "Last Seen", "Action"
        ])
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.device_table)
        
        # Refresh button
        refresh_btn = QPushButton("[REFRESH] Refresh Devices")
        refresh_btn.clicked.connect(self.refresh_devices)
        layout.addWidget(refresh_btn)
        
        # Enhanced device management buttons
        device_mgmt_layout = QHBoxLayout()
        
        history_btn = QPushButton("[HISTORY] Device History")
        history_btn.clicked.connect(self.show_device_history_dialog)
        device_mgmt_layout.addWidget(history_btn)
        
        templates_btn = QPushButton("[TEMPLATES] Templates")
        templates_btn.clicked.connect(self.show_device_templates_dialog)
        device_mgmt_layout.addWidget(templates_btn)
        
        search_btn = QPushButton("[SEARCH] Search")
        search_btn.clicked.connect(self.show_device_search_dialog)
        device_mgmt_layout.addWidget(search_btn)
        
        layout.addLayout(device_mgmt_layout)
        
        return panel
    
    def create_control_panel(self):
        """Create the control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Operator info group
        op_group = QGroupBox("Operator Information")
        op_layout = QVBoxLayout()
        
        op_layout.addWidget(QLabel("Name:"))
        self.operator_name = QLineEdit()
        self.operator_name.setText(self.config.get('operator', {}).get('name', ''))
        op_layout.addWidget(self.operator_name)
        
        op_layout.addWidget(QLabel("Email:"))
        self.operator_email = QLineEdit()
        self.operator_email.setText(self.config.get('operator', {}).get('email', ''))
        op_layout.addWidget(self.operator_email)
        
        op_group.setLayout(op_layout)
        layout.addWidget(op_group)
        
        # Machine info group
        machine_group = QGroupBox("Machine Information")
        machine_layout = QVBoxLayout()
        
        machine_layout.addWidget(QLabel("Machine Type:"))
        self.machine_type = QComboBox()
        self.update_machine_type_combo()
        machine_type_idx = list(Config.get_machine_types(self.config).keys()).index(
            self.config.get('machine_type', 'Amphore')
        )
        self.machine_type.setCurrentIndex(machine_type_idx)
        self.machine_type.currentTextChanged.connect(self.on_machine_type_changed)
        machine_layout.addWidget(self.machine_type)
        
        machine_layout.addWidget(QLabel("Machine ID:"))
        self.machine_id = QLineEdit()
        self.machine_id.setPlaceholderText("Enter machine ID")
        machine_layout.addWidget(self.machine_id)
        
        machine_group.setLayout(machine_layout)
        layout.addWidget(machine_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("[REPORT] Generate Excel Report")
        export_btn.clicked.connect(self.generate_report)
        button_layout.addWidget(export_btn)
        
        email_btn = QPushButton("[EMAIL] Send Email")
        email_btn.clicked.connect(self.send_email)
        button_layout.addWidget(email_btn)
        
        flash_btn = QPushButton("[FLASH] Flash Firmware")
        flash_btn.clicked.connect(self.flash_firmware_dialog)
        button_layout.addWidget(flash_btn)
        
        layout.addLayout(button_layout)
        
        # Settings buttons
        settings_layout = QHBoxLayout()
        
        email_settings_btn = QPushButton("[CONFIG] Configure Email")
        email_settings_btn.clicked.connect(self.configure_email_dialog)
        settings_layout.addWidget(email_settings_btn)
        
        machine_settings_btn = QPushButton("[MACHINE] Machine Types")
        machine_settings_btn.clicked.connect(self.configure_machine_types_dialog)
        settings_layout.addWidget(machine_settings_btn)
        
        onedrive_settings_btn = QPushButton("[ONEDRIVE] OneDrive")
        onedrive_settings_btn.clicked.connect(self.configure_onedrive_dialog)
        settings_layout.addWidget(onedrive_settings_btn)
        
        theme_settings_btn = QPushButton("[THEME] Theme Settings")
        theme_settings_btn.clicked.connect(self.show_theme_settings_dialog)
        settings_layout.addWidget(theme_settings_btn)
        
        theme_lang_btn = QPushButton("[THEME & LANGUAGE] Visual Selection")
        theme_lang_btn.clicked.connect(self.show_theme_language_dialog)
        settings_layout.addWidget(theme_lang_btn)
        
        layout.addLayout(settings_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Log area
        log_label = QLabel("Logs:")
        layout.addWidget(log_label)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(200)
        layout.addWidget(self.log_area)
        
        return panel
    
    def refresh_devices(self):
        """Refresh the device list."""
        self.statusBar().showMessage("Scanning for devices...")
        self.devices = self.device_detector.detect_devices()
        self.update_device_table()
        self.statusBar().showMessage(f"Found {len(self.devices)} device(s)")
    
    def update_device_table(self):
        """Update the device table with current devices."""
        self.device_table.setRowCount(len(self.devices))
        
        for row, device in enumerate(self.devices):
            # Port
            self.device_table.setItem(row, 0, QTableWidgetItem(device.port))
            
            # Type
            self.device_table.setItem(row, 1, QTableWidgetItem(device.board_type.value))
            
            # VID:PID
            vid_pid = f"{device.vid:04X}:{device.pid:04X}" if device.vid and device.pid else "N/A"
            self.device_table.setItem(row, 2, QTableWidgetItem(vid_pid))
            
            # Status
            status_item = QTableWidgetItem(device.status)
            if device.status == "Connected":
                status_item.setBackground(Qt.green)
            elif device.status == "Disconnected":
                status_item.setBackground(Qt.red)
            else:
                status_item.setBackground(Qt.yellow)
            self.device_table.setItem(row, 3, status_item)
            
            # Health Score
            health_score = self.device_detector.get_device_health_score(device)
            health_item = QTableWidgetItem(f"{health_score}%")
            if health_score >= 80:
                health_item.setBackground(Qt.green)
            elif health_score >= 60:
                health_item.setBackground(Qt.yellow)
            else:
                health_item.setBackground(Qt.red)
            self.device_table.setItem(row, 4, health_item)
            
            # Custom Name
            display_name = device.get_display_name()
            self.device_table.setItem(row, 5, QTableWidgetItem(display_name))
            
            # Last Seen
            last_seen = device.last_seen.split('T')[0] if device.last_seen else "Never"
            self.device_table.setItem(row, 6, QTableWidgetItem(last_seen))
            
            # Action button
            btn = QPushButton("Select")
            btn.clicked.connect(lambda checked, d=device: self.select_device(d))
            self.device_table.setCellWidget(row, 7, btn)
    
    def select_device(self, device: Device):
        """Handle device selection."""
        self.log(f"Selected device: {device.port} ({device.board_type.value})")
        self.statusBar().showMessage(f"Selected: {device.port}")
    
    def on_machine_type_changed(self, text):
        """Handle machine type change."""
        # Reset machine ID placeholder with prefix
        machine_types = Config.get_machine_types(self.config)
        if text in machine_types:
            prefix = machine_types[text]['prefix']
            length = machine_types[text]['length']
            remaining = length - len(prefix)
            placeholder = prefix + "X" * remaining
            self.machine_id.setPlaceholderText(f"e.g., {placeholder}")
    
    def generate_report(self):
        """Generate Excel report."""
        try:
            # Validate inputs
            operator_name = self.operator_name.text()
            operator_email = self.operator_email.text()
            machine_id = self.machine_id.text()
            
            if not operator_name or not operator_email or not machine_id:
                QMessageBox.warning(self, "Validation Error", 
                                  "Please fill in all fields")
                return
            
            # Validate machine ID format
            machine_type = self.machine_type.currentText()
            machine_types = Config.get_machine_types(self.config)
            type_config = machine_types[machine_type]
            
            is_valid, error_message = Config.validate_machine_id(machine_id, type_config)
            if not is_valid:
                QMessageBox.warning(self, "Validation Error", error_message)
                return
            
            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Generate report
            operator_info = {
                'name': operator_name,
                'email': operator_email
            }
            
            report_path = self.report_generator.generate_report(
                self.devices, operator_info, machine_type, machine_id
            )
            
            self.last_report_path = report_path  # Store for email sending
            self.progress_bar.setValue(100)
            
            # Save to OneDrive if enabled
            if self.onedrive_manager.is_enabled():
                self.log("Syncing data to OneDrive...")
                success = self.onedrive_manager.save_machine_data(
                    operator_name=operator_name,
                    machine_type=machine_type,
                    machine_id=machine_id,
                    devices=self.devices
                )
                if success:
                    self.log("[SUCCESS] Data synced to OneDrive successfully")
                else:
                    self.log("[WARNING] OneDrive sync failed - check logs")
            
            # Ask user to confirm data and send email
            reply = QMessageBox.question(
                self,
                "Report Generated Successfully",
                f"Report generated:\n{report_path}\n\n"
                f"Data Summary:\n"
                f"- Operator: {operator_name}\n"
                f"- Machine Type: {machine_type}\n"
                f"- Machine ID: {machine_id}\n"
                f"- Devices: {len(self.devices)}\n\n"
                "Is the data correct?\n"
                "Click 'Yes' to send email automatically,\n"
                "or 'No' to keep the report only.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # User confirmed - send email automatically
                self.send_email_automatically()
            else:
                # User chose not to send
                QMessageBox.information(self, "Report Saved",
                                      "Report saved locally.")
            
            # Update config
            self.save_operator_info()
            
        except Exception as e:
            self.log(f"Error generating report: {e}")
            QMessageBox.critical(self, "Error", f"Failed to generate report: {e}")
        finally:
            self.progress_bar.setVisible(False)
    
    def send_email(self):
        """Send email with report (manual trigger)."""
        if not self.last_report_path or not self.last_report_path.exists():
            QMessageBox.warning(self, "No Report", 
                              "Please generate a report first.")
            return
        
        # Check if SMTP is configured
        smtp_config = self.config.get('smtp', {})
        if not smtp_config.get('host'):
            reply = QMessageBox.question(
                self,
                "Email Not Configured",
                "Email is not configured. Would you like to configure it now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.configure_email_dialog()
                return
        
        self.send_email_automatically()
    
    def send_email_automatically(self):
        """Automatically send email with the last generated report."""
        if not self.last_report_path or not self.last_report_path.exists():
            QMessageBox.warning(self, "No Report", 
                              "No report available to send.")
            return
        
        smtp_config = self.config.get('smtp', {})
        recipients = self.config.get('recipients', [])
        
        # Check configuration
        if not smtp_config.get('host'):
            QMessageBox.warning(self, "Email Not Configured",
                              "Please configure SMTP settings first.")
            return
        
        if not recipients:
            QMessageBox.warning(self, "No Recipients",
                              "Please add email recipients in settings.")
            return
        
        if not smtp_config.get('username'):
            QMessageBox.warning(self, "Email Not Configured",
                              "SMTP username not configured.")
            return
        
        try:
            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Update progress in log
            def update_progress(msg):
                self.log(msg)
                self.progress_bar.setValue(self.progress_bar.value() + 25)
            
            update_progress("Connecting to SMTP server...")
            
            # Get operator info for email body
            operator_name = self.operator_name.text()
            operator_email = self.operator_email.text()
            machine_type = self.machine_type.currentText()
            machine_id = self.machine_id.text()
            
            # Create detailed device summary for email
            device_summary = self._create_device_summary()
            
            email_body = f"""AWG Kumulus Device Manager Report

Operator: {operator_name} ({operator_email})
Machine Type: {machine_type}
Machine ID: {machine_id}
Devices Detected: {len(self.devices)}

DEVICE DETAILS:
{device_summary}

Please find the attached Excel report with complete device information including UIDs, hardware characteristics, and technical specifications."""
            
            update_progress("Sending email...")
            
            # Send email
            success = self.email_sender.send_email(
                smtp_config=smtp_config,
                recipients=recipients,
                subject=f"AWG Kumulus Report - {machine_type} - {machine_id}",
                body=email_body,
                attachment_path=self.last_report_path,
                progress_callback=update_progress
            )
            
            self.progress_bar.setValue(100)
            
            if success:
                update_progress("Email sent successfully!")
                QMessageBox.information(self, "Email Sent",
                                      f"Report sent successfully to:\n" +
                                      "\n".join(recipients))
            else:
                QMessageBox.warning(self, "Email Failed",
                                  "Failed to send email. Check logs for details.")
            
        except Exception as e:
            self.log(f"Error sending email: {e}")
            QMessageBox.critical(self, "Error", 
                               f"Failed to send email:\n{str(e)}")
        finally:
            self.progress_bar.setVisible(False)
    
    def _create_device_summary(self) -> str:
        """Create a detailed summary of detected devices for email."""
        if not self.devices:
            return "No devices detected."
        
        summary_lines = []
        for i, device in enumerate(self.devices, 1):
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
                f"  VID:PID: 0x{device.vid:04X}:0x{device.pid:04X}" if device.vid and device.pid else "  VID:PID: N/A",
                ""
            ]
            summary_lines.extend(device_info)
        
        return "\n".join(summary_lines)
    
    def configure_email_dialog(self):
        """Open email configuration dialog with preset configurations and auto-detection."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Email Configuration")
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        
        # Email Provider Selection
        provider_group = QGroupBox("Email Provider")
        provider_layout = QVBoxLayout()
        
        # Provider selection
        provider_layout.addWidget(QLabel("Choose your email provider:"))
        provider_combo = QComboBox()
        provider_combo.addItems(["Auto-detect from email", "Gmail", "Outlook/Hotmail", "Office 365", "Custom"])
        provider_layout.addWidget(provider_combo)
        
        # Email Username (for auto-detection)
        layout.addWidget(QLabel("Email Address:"))
        smtp_user = QLineEdit()
        smtp_user.setText(self.config.get('smtp', {}).get('username', ''))
        smtp_user.setPlaceholderText("your.email@gmail.com")
        layout.addWidget(smtp_user)
        
        # Auto-detect button
        auto_detect_btn = QPushButton("[AUTO-DETECT] Auto-detect Settings")
        auto_detect_btn.setMaximumWidth(150)
        layout.addWidget(auto_detect_btn)
        
        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)
        
        # SMTP Configuration Group
        smtp_group = QGroupBox("SMTP Configuration")
        smtp_layout = QVBoxLayout()
        
        # SMTP Server
        smtp_layout.addWidget(QLabel("SMTP Server:"))
        smtp_host = QLineEdit()
        smtp_host.setText(self.config.get('smtp', {}).get('host', ''))
        smtp_host.setPlaceholderText("e.g., smtp.gmail.com")
        smtp_layout.addWidget(smtp_host)
        
        # Port
        smtp_layout.addWidget(QLabel("Port:"))
        smtp_port = QLineEdit()
        smtp_port.setText(str(self.config.get('smtp', {}).get('port', 587)))
        smtp_layout.addWidget(smtp_port)
        
        # TLS checkbox
        tls_checkbox = QCheckBox("Use TLS/STARTTLS")
        tls_checkbox.setChecked(self.config.get('smtp', {}).get('tls', True))
        smtp_layout.addWidget(tls_checkbox)
        
        smtp_group.setLayout(smtp_layout)
        layout.addWidget(smtp_group)
        
        # Password
        layout.addWidget(QLabel("Password (stored securely):"))
        smtp_pass = QLineEdit()
        smtp_pass.setEchoMode(QLineEdit.Password)
        layout.addWidget(smtp_pass)
        
        # Recipients
        layout.addWidget(QLabel("Recipients (one per line):"))
        recipients_text = QTextEdit()
        recipients_text.setMaximumHeight(100)
        recipients_text.setPlainText("\n".join(self.config.get('recipients', [])))
        layout.addWidget(recipients_text)
        
        # Dynamic Configuration Guide
        guide_group = QGroupBox("[GUIDE] Email Configuration Guide")
        guide_layout = QVBoxLayout()
        
        # Dynamic guide label that changes based on provider selection
        self.dynamic_guide = QLabel("Select an email provider to see specific configuration instructions")
        self.dynamic_guide.setOpenExternalLinks(True)
        self.dynamic_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0f8ff; padding: 8px; border-radius: 4px; border: 1px solid #b0d4f1;")
        guide_layout.addWidget(self.dynamic_guide)
        
        guide_group.setLayout(guide_layout)
        layout.addWidget(guide_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        # Connect signals for auto-detection and preset configurations
        def auto_detect_settings():
            """Auto-detect SMTP settings based on email domain."""
            email = smtp_user.text().strip()
            if not email:
                QMessageBox.warning(dialog, "No Email", "Please enter your email address first.")
                return
            
            # Extract domain
            if '@' not in email:
                QMessageBox.warning(dialog, "Invalid Email", "Please enter a valid email address.")
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
                QMessageBox.information(dialog, "Custom Domain", 
                    f"Domain '{domain}' not recognized. Please configure manually or choose 'Custom'.")
                provider_combo.setCurrentText('Custom')
            
            # Update the guide after auto-detection
            update_dynamic_guide()
        
        def apply_preset_config():
            """Apply preset configuration based on selected provider."""
            provider = provider_combo.currentText()
            
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
            elif provider == 'Custom':
                # Clear fields for custom configuration
                smtp_host.clear()
                smtp_port.setText('587')
                tls_checkbox.setChecked(True)
        
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
            if provider == 'Gmail':
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
        
        if dialog.exec():
            # Save configuration
            self.config['smtp'] = {
                'host': smtp_host.text(),
                'port': int(smtp_port.text() or 587),
                'tls': tls_checkbox.isChecked(),
                'username': smtp_user.text()
            }
            
            # Save password to keyring
            if smtp_pass.text():
                self.email_sender.save_credentials(smtp_user.text(), smtp_pass.text())
            
            # Save recipients
            recipients = [r.strip() for r in recipients_text.toPlainText().split('\n') if r.strip()]
            self.config['recipients'] = recipients
            
            Config.save_config(self.config)
            
            QMessageBox.information(self, "Configuration Saved",
                                  "Email configuration saved successfully!")
    
    def flash_firmware_dialog(self):
        """Open firmware flashing dialog."""
        if not self.devices:
            QMessageBox.warning(self, "No Devices", "No devices detected")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Flash Firmware")
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        
        # Device Selection
        device_group = QGroupBox("Select Device")
        device_layout = QVBoxLayout()
        
        device_layout.addWidget(QLabel("Choose device to flash:"))
        device_list = QListWidget()
        
        for device in self.devices:
            item_text = f"{device.board_type.value} - {device.port}"
            if device.manufacturer:
                item_text += f" ({device.manufacturer})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, device)
            device_list.addItem(item)
        
        device_list.setCurrentRow(0)  # Select first device
        device_layout.addWidget(device_list)
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)
        
        # Firmware Source Selection
        firmware_group = QGroupBox("Firmware Source")
        firmware_layout = QVBoxLayout()
        
        # Source type selection
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source Type:"))
        source_combo = QComboBox()
        source_combo.addItems(["Local File (.bin/.elf)", "URL Download", "GitLab Repository"])
        source_layout.addWidget(source_combo)
        firmware_layout.addLayout(source_layout)
        
        # File selection
        file_layout = QHBoxLayout()
        file_path = QLineEdit()
        file_path.setPlaceholderText("Select firmware file or enter URL...")
        file_layout.addWidget(file_path)
        
        browse_btn = QPushButton("[BROWSE] Browse")
        browse_btn.clicked.connect(lambda: self._browse_firmware_file(file_path))
        file_layout.addWidget(browse_btn)
        firmware_layout.addLayout(file_layout)
        
        # Firmware Configuration Guide
        firmware_guide_group = QGroupBox("[GUIDE] Firmware Flashing Guide")
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
        board_guide = QLabel("""
        <b>[BOARD] Board-Specific Requirements:</b><br>
        • <b>ESP32/ESP8266:</b> Requires esptool, supports .bin files<br>
        • <b>STM32:</b> Requires STM32CubeProgrammer or OpenOCD<br>
        • <b>Arduino:</b> Uses avrdude for AVR-based boards<br>
        • <b>Generic:</b> Basic serial communication support
        """)
        board_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff0f0; padding: 8px; border-radius: 4px; border: 1px solid #f1b0b0;")
        firmware_guide_layout.addWidget(board_guide)
        
        # Troubleshooting Guide
        firmware_troubleshooting_guide = QLabel("""
        <b>[TROUBLESHOOTING] Firmware Flashing Troubleshooting:</b><br>
        • <b>Device not found:</b> Check USB connection and drivers<br>
        • <b>Permission denied:</b> Run as administrator (Windows) or use sudo (Linux)<br>
        • <b>Flash failed:</b> Put device in bootloader mode manually<br>
        • <b>Wrong file format:</b> Ensure file matches board type<br>
        • <b>Still having issues?</b> Check: <a href="https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/">ESP32 Docs</a> | <a href="https://www.st.com/en/development-tools/stm32cubeprog.html">STM32 Docs</a>
        """)
        firmware_troubleshooting_guide.setOpenExternalLinks(True)
        firmware_troubleshooting_guide.setStyleSheet("color: #333; font-size: 10px; background: #fff8f0; padding: 8px; border-radius: 4px; border: 1px solid #f1d0b0;")
        firmware_guide_layout.addWidget(firmware_troubleshooting_guide)
        
        firmware_guide_group.setLayout(firmware_guide_layout)
        layout.addWidget(firmware_guide_group)
        
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
        flash_btn.setText("[FLASH] Flash Firmware")
        flash_btn.clicked.connect(lambda: self._start_flashing(
            dialog, device_list.currentItem().data(Qt.UserRole),
            file_path.text(), erase_checkbox.isChecked(),
            verify_checkbox.isChecked(), boot_combo.currentText()
        ))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec():
            pass  # Dialog was accepted
    
    def _browse_firmware_file(self, file_path_widget):
        """Browse for firmware file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Firmware File",
            "",
            "Firmware Files (*.bin *.elf);;Binary Files (*.bin);;ELF Files (*.elf);;All Files (*)"
        )
        if file_path:
            file_path_widget.setText(file_path)
    
    def _create_source_inputs(self):
        """Create source input widgets for firmware dialog."""
        self.source_inputs = {}
        
        # Local file input
        local_layout = QVBoxLayout()
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("File Path:"))
        firmware_path = QLineEdit()
        firmware_path.setPlaceholderText("Enter file path...")
        file_layout.addWidget(firmware_path)
        
        browse_btn = QPushButton("[BROWSE] Browse")
        browse_btn.clicked.connect(lambda: self._browse_firmware_file(firmware_path))
        file_layout.addWidget(browse_btn)
        local_layout.addLayout(file_layout)
        self.source_inputs["Local File"] = local_layout
        
        # GitHub input
        github_layout = QVBoxLayout()
        github_repo_layout = QHBoxLayout()
        github_repo_layout.addWidget(QLabel("Repository (owner/repo):"))
        github_repo = QLineEdit()
        github_repo.setPlaceholderText("e.g., espressif/arduino-esp32")
        github_repo_layout.addWidget(github_repo)
        github_layout.addLayout(github_repo_layout)
        
        github_release_layout = QHBoxLayout()
        github_release_layout.addWidget(QLabel("Release Tag (optional):"))
        github_release = QLineEdit()
        github_release.setPlaceholderText("Leave empty for latest")
        github_release_layout.addWidget(github_release)
        github_layout.addLayout(github_release_layout)
        
        github_asset_layout = QHBoxLayout()
        github_asset_layout.addWidget(QLabel("Asset Name (optional):"))
        github_asset = QLineEdit()
        github_asset.setPlaceholderText("Leave empty for auto-detect")
        github_asset_layout.addWidget(github_asset)
        github_layout.addLayout(github_asset_layout)
        
        self.source_inputs["GitHub Release"] = github_layout
        
        # GitLab input
        gitlab_layout = QVBoxLayout()
        gitlab_project_layout = QHBoxLayout()
        gitlab_project_layout.addWidget(QLabel("Project ID:"))
        gitlab_project = QLineEdit()
        gitlab_project.setPlaceholderText("e.g., 12345")
        gitlab_project_layout.addWidget(gitlab_project)
        gitlab_layout.addLayout(gitlab_project_layout)
        
        gitlab_pipeline_layout = QHBoxLayout()
        gitlab_pipeline_layout.addWidget(QLabel("Pipeline ID (optional):"))
        gitlab_pipeline = QLineEdit()
        gitlab_pipeline.setPlaceholderText("Leave empty for latest")
        gitlab_pipeline_layout.addWidget(gitlab_pipeline)
        gitlab_layout.addLayout(gitlab_pipeline_layout)
        
        gitlab_artifact_layout = QHBoxLayout()
        gitlab_artifact_layout.addWidget(QLabel("Artifact Name (optional):"))
        gitlab_artifact = QLineEdit()
        gitlab_artifact.setPlaceholderText("Leave empty for auto-detect")
        gitlab_artifact_layout.addWidget(gitlab_artifact)
        gitlab_layout.addLayout(gitlab_artifact_layout)
        
        self.source_inputs["GitLab Pipeline"] = gitlab_layout
        
        # URL input
        url_layout = QVBoxLayout()
        url_input_layout = QHBoxLayout()
        url_input_layout.addWidget(QLabel("URL:"))
        firmware_url = QLineEdit()
        firmware_url.setPlaceholderText("https://example.com/firmware.bin")
        url_input_layout.addWidget(firmware_url)
        url_layout.addLayout(url_input_layout)
        
        url_name_layout = QHBoxLayout()
        url_name_layout.addWidget(QLabel("Name:"))
        firmware_name = QLineEdit()
        firmware_name.setPlaceholderText("Firmware Name")
        url_name_layout.addWidget(firmware_name)
        url_layout.addLayout(url_name_layout)
        
        url_version_layout = QHBoxLayout()
        url_version_layout.addWidget(QLabel("Version:"))
        firmware_version = QLineEdit()
        firmware_version.setPlaceholderText("1.0.0")
        url_version_layout.addWidget(firmware_version)
        url_layout.addLayout(url_version_layout)
        
        self.source_inputs["URL Download"] = url_layout
        
        # Database input
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Select Firmware:"))
        firmware_combo = QComboBox()
        db_layout.addWidget(firmware_combo)
        self.source_inputs["Firmware Database"] = db_layout
    
    def _start_enhanced_flashing(self, dialog, device_list, source_combo, erase_checkbox, 
                                verify_checkbox, backup_checkbox, progress_bar, status_label):
        """Start enhanced firmware flashing process."""
        current_item = device_list.currentItem()
        if not current_item:
            QMessageBox.warning(dialog, "No Device", "Please select a device")
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
                    QMessageBox.warning(dialog, "No File", "Please select a firmware file")
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
                    QMessageBox.warning(dialog, "No Repository", "Please enter GitHub repository")
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
                    QMessageBox.warning(dialog, "No Firmware", "Please select firmware from database")
                    return
                
                # Flash from database
                self._flash_from_database(device, firmware_id,
                                        erase_checkbox.isChecked(), verify_checkbox.isChecked(),
                                        backup_checkbox.isChecked(), progress_bar, status_label)
        
        except Exception as e:
            status_label.setText(f"Error: {str(e)}")
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
                status_label.setText("[ERROR] Firmware flashing failed!")
                status_label.setStyleSheet("color: red;")
        
        except Exception as e:
            status_label.setText(f"[ERROR] Error: {str(e)}")
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
            progress_callback("Connecting to GitLab...")
            
            # Flash from GitLab
            success = self.firmware_flasher.flash_from_gitlab(
                device, project_id, pipeline_id, artifact_name, progress_callback
            )
            
            if success:
                progress_bar.setValue(100)
                status_label.setText("[SUCCESS] GitLab firmware flashed successfully!")
                status_label.setStyleSheet("color: green;")
            else:
                status_label.setText("[ERROR] GitLab firmware flashing failed!")
                status_label.setStyleSheet("color: red;")
        
        except Exception as e:
            status_label.setText(f"[ERROR] Error: {str(e)}")
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
            progress_callback("Loading firmware from database...")
            
            # Flash from database
            success = self.firmware_flasher.flash_firmware_by_id(
                device, firmware_id, progress_callback
            )
            
            if success:
                progress_bar.setValue(100)
                status_label.setText("[SUCCESS] Database firmware flashed successfully!")
                status_label.setStyleSheet("color: green;")
            else:
                status_label.setText("[ERROR] Database firmware flashing failed!")
                status_label.setStyleSheet("color: red;")
        
        except Exception as e:
            status_label.setText(f"[ERROR] Error: {str(e)}")
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
            QMessageBox.warning(self, "No Device", "Please select a device")
            return
        
        device = current_item.data(Qt.UserRole)
        
        if not hasattr(self, 'backups_list'):
            QMessageBox.warning(self, "No Backups", "No backups list available")
            return
        
        backup_item = self.backups_list.currentItem()
        if not backup_item:
            QMessageBox.warning(self, "No Backup", "Please select a backup to rollback to")
            return
        
        backup_data = backup_item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "Confirm Rollback",
            f"Are you sure you want to rollback to {backup_data['firmware_info']['version']}?",
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
                    QMessageBox.information(self, "Success", "Firmware rollback completed successfully!")
                    self._update_firmware_status(device_list)
                else:
                    QMessageBox.warning(self, "Failed", "Firmware rollback failed!")
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Rollback error: {str(e)}")
                logger.error(f"Rollback error: {e}")
    
    def _start_flashing(self, dialog, device, firmware_source, erase_flash, verify_flash, boot_mode):
        """Start the firmware flashing process."""
        if not firmware_source.strip():
            QMessageBox.warning(dialog, "No Firmware", "Please select a firmware file or enter URL")
            return
        
        if not device:
            QMessageBox.warning(dialog, "No Device", "Please select a device")
            return
        
        # Show progress
        self.flash_progress.setVisible(True)
        self.flash_progress.setValue(0)
        self.flash_status.setText("Preparing to flash...")
        
        # Update progress callback
        def update_progress(msg):
            self.flash_status.setText(msg)
            self.flash_progress.setValue(self.flash_progress.value() + 20)
            dialog.repaint()
        
        try:
            # Start flashing in a separate thread
            self.flash_thread = WorkerThread(
                self._flash_firmware_worker,
                device, firmware_source, erase_flash, verify_flash, boot_mode, update_progress
            )
            self.flash_thread.finished.connect(lambda: self._flash_completed(dialog, True))
            self.flash_thread.error.connect(lambda error: self._flash_completed(dialog, False, error))
            self.flash_thread.start()
            
        except Exception as e:
            QMessageBox.critical(dialog, "Flash Error", f"Failed to start flashing: {str(e)}")
            self.flash_progress.setVisible(False)
    
    def _flash_firmware_worker(self, device, firmware_source, erase_flash, verify_flash, boot_mode, progress_callback):
        """Worker function for firmware flashing."""
        try:
            progress_callback("Initializing firmware flasher...")
            
            # Flash the firmware
            success = self.firmware_flasher.flash_firmware(
                device=device,
                firmware_source=firmware_source,
                progress_callback=progress_callback
            )
            
            if success:
                progress_callback("Firmware flashed successfully!")
                
                # Save firmware to OneDrive if enabled
                if self.onedrive_manager.is_enabled():
                    progress_callback("Saving firmware to OneDrive...")
                    firmware_info = {
                        "name": firmware_path.name,
                        "version": "Unknown",
                        "path": str(firmware_path),
                        "url": "",
                        "size": firmware_path.stat().st_size if firmware_path.exists() else 0,
                        "hash": ""
                    }
                    
                    onedrive_success = self.onedrive_manager.save_firmware_file(
                        operator_name=self.operator_name.text(),
                        machine_type=self.machine_type.currentText(),
                        machine_id=self.machine_id.text(),
                        firmware_path=firmware_path,
                        firmware_info=firmware_info
                    )
                    
                    if onedrive_success:
                        progress_callback("[SUCCESS] Firmware saved to OneDrive")
                    else:
                        progress_callback("[WARNING] OneDrive firmware save failed")
            else:
                raise Exception("Firmware flashing failed")
                
        except Exception as e:
            raise Exception(f"Flashing error: {str(e)}")
    
    def update_machine_type_combo(self):
        """Update machine type combo box with current config."""
        self.machine_type.clear()
        machine_types = Config.get_machine_types(self.config)
        self.machine_type.addItems(list(machine_types.keys()))
    
    def configure_machine_types_dialog(self):
        """Open machine types configuration dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Machine Types Configuration")
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # Machine Types Management Tab
        machine_tab = QWidget()
        machine_layout = QVBoxLayout()
        
        # Machine types list
        list_group = QGroupBox("Machine Types")
        list_layout = QVBoxLayout()
        
        self.machine_types_list = QListWidget()
        self.populate_machine_types_list()
        list_layout.addWidget(self.machine_types_list)
        
        # Machine type buttons
        machine_buttons_layout = QHBoxLayout()
        
        add_btn = QPushButton("[ADD] Add New")
        add_btn.clicked.connect(lambda: self.add_machine_type_dialog(dialog))
        machine_buttons_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("[EDIT] Edit")
        edit_btn.clicked.connect(lambda: self.edit_machine_type_dialog(dialog))
        machine_buttons_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("[DELETE] Delete")
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
        examples_guide.setStyleSheet("color: #333; font-size: 10px; background: #f0fff0; padding: 8px; border-radius: 4px; border: 1px solid #b0f1b0;")
        machine_guide_layout.addWidget(examples_guide)
        
        machine_guide_group.setLayout(machine_guide_layout)
        machine_layout.addWidget(machine_guide_group)
        
        machine_tab.setLayout(machine_layout)
        tab_widget.addTab(machine_tab, "Machine Types")
        
        # Validation Tab
        validation_tab = QWidget()
        validation_layout = QVBoxLayout()
        
        # Test machine ID validation
        test_group = QGroupBox("Test Machine ID Validation")
        test_layout = QVBoxLayout()
        
        test_layout.addWidget(QLabel("Select machine type and enter ID to test:"))
        
        test_type_layout = QHBoxLayout()
        test_type_layout.addWidget(QLabel("Machine Type:"))
        self.test_machine_type = QComboBox()
        self.test_machine_type.addItems(list(Config.get_machine_types(self.config).keys()))
        test_type_layout.addWidget(self.test_machine_type)
        test_layout.addLayout(test_type_layout)
        
        test_id_layout = QHBoxLayout()
        test_id_layout.addWidget(QLabel("Machine ID:"))
        self.test_machine_id = QLineEdit()
        self.test_machine_id.setPlaceholderText("Enter machine ID to test...")
        test_id_layout.addWidget(self.test_machine_id)
        test_layout.addLayout(test_id_layout)
        
        test_btn = QPushButton("[TEST] Test Validation")
        test_btn.clicked.connect(self.test_machine_id_validation)
        test_layout.addWidget(test_btn)
        
        self.validation_result = QLabel("Enter a machine ID to test validation")
        self.validation_result.setStyleSheet("color: #666; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        test_layout.addWidget(self.validation_result)
        
        test_group.setLayout(test_layout)
        validation_layout.addWidget(test_group)
        
        validation_tab.setLayout(validation_layout)
        tab_widget.addTab(validation_tab, "Validation Test")
        
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
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # OneDrive Settings Tab
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        
        # Enable OneDrive
        enable_group = QGroupBox("OneDrive Integration")
        enable_layout = QVBoxLayout()
        
        self.onedrive_enabled = QCheckBox("Enable OneDrive Integration")
        self.onedrive_enabled.setChecked(self.config.get('onedrive', {}).get('enabled', False))
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
        folder_layout.addWidget(self.onedrive_folder_path)
        
        browse_folder_btn = QPushButton("[BROWSE] Browse")
        browse_folder_btn.clicked.connect(self._browse_onedrive_folder)
        folder_layout.addWidget(browse_folder_btn)
        path_layout.addLayout(folder_layout)
        
        # User folder name
        path_layout.addWidget(QLabel("User Folder Name:"))
        self.user_folder_name = QLineEdit()
        self.user_folder_name.setText(self.config.get('onedrive', {}).get('user_folder', ''))
        self.user_folder_name.setPlaceholderText("e.g., JohnDoe_Work")
        path_layout.addWidget(self.user_folder_name)
        
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
        
        test_btn = QPushButton("[TEST] Test OneDrive Connection")
        test_btn.clicked.connect(self.test_onedrive_connection)
        test_layout.addWidget(test_btn)
        
        self.onedrive_test_result = QLabel("Click 'Test Connection' to verify OneDrive access")
        self.onedrive_test_result.setStyleSheet("color: #666; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        test_layout.addWidget(self.onedrive_test_result)
        
        test_group.setLayout(test_layout)
        settings_layout.addWidget(test_group)
        
        # OneDrive Configuration Guide
        onedrive_guide_group = QGroupBox("[GUIDE] OneDrive Configuration Guide")
        onedrive_guide_layout = QVBoxLayout()
        
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
        onedrive_guide_layout.addWidget(onedrive_setup_guide)
        
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
        onedrive_guide_layout.addWidget(cloud_alternatives_guide)
        
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
        onedrive_guide_layout.addWidget(onedrive_troubleshooting_guide)
        
        onedrive_guide_group.setLayout(onedrive_guide_layout)
        settings_layout.addWidget(onedrive_guide_group)
        
        settings_tab.setLayout(settings_layout)
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
        
        refresh_history_btn = QPushButton("[REFRESH] Refresh History")
        refresh_history_btn.clicked.connect(self.populate_machine_history)
        history_list_layout.addWidget(refresh_history_btn)
        
        history_group.setLayout(history_list_layout)
        history_layout.addWidget(history_group)
        
        history_tab.setLayout(history_layout)
        tab_widget.addTab(history_tab, "Machine History")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: self.save_onedrive_settings(dialog))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
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
            self.onedrive_test_result.setStyleSheet("color: green; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        else:
            self.onedrive_test_result.setText(f"[ERROR] {message}")
            self.onedrive_test_result.setStyleSheet("color: red; font-size: 12px; padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
    
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
    
    def save_operator_info(self):
        """Save operator information to config."""
        self.config['operator'] = {
            'name': self.operator_name.text(),
            'email': self.operator_email.text()
        }
        self.config['machine_type'] = self.machine_type.currentText()
        Config.save_config(self.config)
    
    def center_window(self):
        """Center the window on the primary screen."""
        from PySide6.QtWidgets import QApplication
        
        screen = QApplication.primaryScreen().geometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)
    
    def log(self, message: str):
        """Add a log message to the log area."""
        self.log_area.append(message)
        logger.info(message)
    
    def show_first_run_dialog(self):
        """Show first run setup dialog."""
        manager = BootstrapManager()
        success, warnings = manager.run_first_run_setup()
        
        if warnings:
            msg = "\n".join(warnings)
            QMessageBox.information(self, "First Run Setup",
                                  f"Setup completed with warnings:\n{msg}")
    
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
    
    def _handle_device_disconnected(self, device: Device):
        """Handle device disconnection in main thread."""
        self.log(f"[DISCONNECTED] Device disconnected: {device.get_display_name()}")
        self.refresh_devices()  # Refresh the device table
    
    def on_theme_changed(self, theme_name: str):
        """Handle theme change."""
        self.log(f"[THEME] Theme changed to: {theme_name}")
        # Apply additional stylesheet if needed
        app = QApplication.instance()
        if app:
            stylesheet = self.theme_manager.get_theme_stylesheet(ThemeType(theme_name.split('_')[0]))
            app.setStyleSheet(stylesheet)
    
    def on_language_changed(self, language_name: str):
        """Handle language change."""
        self.log(f"[LANGUAGE] Language changed to: {language_name}")
        # Update UI text with new language
        self.update_ui_text()
        # Apply RTL layout if needed
        if self.language_manager.is_rtl_language():
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)
    
    def update_ui_text(self):
        """Update UI text with current language."""
        # Update window title
        self.setWindowTitle(self.language_manager.get_text("app_title"))
        
        # Update button texts
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.setText(f"[{self.language_manager.get_text('refresh')}] {self.language_manager.get_text('refresh_devices')}")
        
        # Update other UI elements as needed
        # This is a simplified version - in a full implementation,
        # you would update all text elements throughout the UI
    
    def show_theme_settings_dialog(self):
        """Show theme settings dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Theme Settings")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Current theme info
        current_theme = self.theme_manager.get_current_theme()
        current_label = QLabel(f"Current Theme: {current_theme.title()}")
        current_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(current_label)
        
        # Theme selection
        theme_group = QGroupBox("Select Theme")
        theme_layout = QVBoxLayout()
        
        # Available themes
        themes = self.theme_manager.get_available_themes()
        theme_combo = QComboBox()
        for display_name, theme_value in themes.items():
            theme_combo.addItem(display_name, theme_value)
        
        # Set current theme
        for i in range(theme_combo.count()):
            if theme_combo.itemData(i) == current_theme:
                theme_combo.setCurrentIndex(i)
                break
        
        theme_layout.addWidget(theme_combo)
        
        # Apply button
        apply_btn = QPushButton("[APPLY] Apply Theme")
        apply_btn.clicked.connect(lambda: self.apply_selected_theme(theme_combo, dialog))
        theme_layout.addWidget(apply_btn)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # Custom theme creation
        custom_group = QGroupBox("Create Custom Theme")
        custom_layout = QVBoxLayout()
        
        # Theme name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Theme Name:"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter custom theme name...")
        name_layout.addWidget(name_input)
        custom_layout.addLayout(name_layout)
        
        # Color selection
        colors_layout = QGridLayout()
        colors_layout.addWidget(QLabel("Window Color:"), 0, 0)
        window_color_btn = QPushButton("Choose Color")
        window_color_btn.clicked.connect(lambda: self.choose_color(window_color_btn, "window"))
        colors_layout.addWidget(window_color_btn, 0, 1)
        
        colors_layout.addWidget(QLabel("Text Color:"), 1, 0)
        text_color_btn = QPushButton("Choose Color")
        text_color_btn.clicked.connect(lambda: self.choose_color(text_color_btn, "text"))
        colors_layout.addWidget(text_color_btn, 1, 1)
        
        colors_layout.addWidget(QLabel("Button Color:"), 2, 0)
        button_color_btn = QPushButton("Choose Color")
        button_color_btn.clicked.connect(lambda: self.choose_color(button_color_btn, "button"))
        colors_layout.addWidget(button_color_btn, 2, 1)
        
        colors_layout.addWidget(QLabel("Highlight Color:"), 3, 0)
        highlight_color_btn = QPushButton("Choose Color")
        highlight_color_btn.clicked.connect(lambda: self.choose_color(highlight_color_btn, "highlight"))
        colors_layout.addWidget(highlight_color_btn, 3, 1)
        
        custom_layout.addLayout(colors_layout)
        
        # Create custom theme button
        create_btn = QPushButton("[CREATE] Create Custom Theme")
        create_btn.clicked.connect(lambda: self.create_custom_theme(name_input, {
            'window': window_color_btn.text(),
            'text': text_color_btn.text(),
            'button': button_color_btn.text(),
            'highlight': highlight_color_btn.text()
        }, dialog))
        custom_layout.addWidget(create_btn)
        
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def apply_selected_theme(self, theme_combo: QComboBox, dialog: QDialog):
        """Apply selected theme."""
        theme_value = theme_combo.currentData()
        if theme_value:
            self.theme_manager.apply_theme_by_name(theme_value)
            QMessageBox.information(dialog, "Theme Applied", f"Theme '{theme_combo.currentText()}' has been applied!")
    
    def choose_color(self, button: QPushButton, color_type: str):
        """Choose color for custom theme."""
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            button.setText(color.name())
            button.setStyleSheet(f"background-color: {color.name()}; color: {'white' if color.lightness() < 128 else 'black'};")
    
    def create_custom_theme(self, name_input: QLineEdit, colors: Dict[str, str], dialog: QDialog):
        """Create custom theme."""
        name = name_input.text().strip()
        if not name:
            QMessageBox.warning(dialog, "Invalid Name", "Please enter a theme name.")
            return
        
        # Convert button texts to color values
        color_dict = {}
        for key, value in colors.items():
            if value.startswith('#'):
                color_dict[key] = value
            else:
                # Default colors if not set
                defaults = {
                    'window': '#FFFFFF',
                    'text': '#000000',
                    'button': '#F0F0F0',
                    'highlight': '#2A82DA'
                }
                color_dict[key] = defaults.get(key, '#FFFFFF')
        
        self.theme_manager.create_custom_theme(name, color_dict, f"Custom theme: {name}")
        QMessageBox.information(dialog, "Theme Created", f"Custom theme '{name}' has been created!")
        dialog.accept()
    
    def show_theme_language_dialog(self):
        """Show visual theme and language selection dialog."""
        dialog = ThemeLanguageSelectionDialog(self.theme_manager, self.language_manager, self)
        if dialog.exec() == QDialog.Accepted:
            self.log("[SETTINGS] Theme and language selection applied")
            QMessageBox.information(self, "Settings Applied", 
                                  "Theme and language settings have been applied successfully!")
    
    def show_device_history_dialog(self):
        """Show device history dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Device History")
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)
        
        layout = QVBoxLayout()
        
        # Device history table
        history_table = QTableWidget()
        history_table.setColumnCount(7)
        history_table.setHorizontalHeaderLabels([
            "Name", "Type", "Port", "Status", "Health", "Last Seen", "Connections"
        ])
        
        # Populate history
        device_history = self.device_detector.get_device_history()
        history_table.setRowCount(len(device_history))
        
        for row, (device_id, device) in enumerate(device_history.items()):
            history_table.setItem(row, 0, QTableWidgetItem(device.get_display_name()))
            history_table.setItem(row, 1, QTableWidgetItem(device.board_type.value))
            history_table.setItem(row, 2, QTableWidgetItem(device.port))
            history_table.setItem(row, 3, QTableWidgetItem(device.status))
            
            health_score = self.device_detector.get_device_health_score(device)
            health_item = QTableWidgetItem(f"{health_score}%")
            if health_score >= 80:
                health_item.setBackground(Qt.green)
            elif health_score >= 60:
                health_item.setBackground(Qt.yellow)
            else:
                health_item.setBackground(Qt.red)
            history_table.setItem(row, 4, health_item)
            
            last_seen = device.last_seen.split('T')[0] if device.last_seen else "Never"
            history_table.setItem(row, 5, QTableWidgetItem(last_seen))
            history_table.setItem(row, 6, QTableWidgetItem(str(device.connection_count)))
        
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
    
    def show_device_templates_dialog(self):
        """Show device templates dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Device Templates")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
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
        
        create_btn = QPushButton("[CREATE] Create from Current")
        create_btn.clicked.connect(lambda: self.create_template_from_current(dialog))
        template_buttons.addWidget(create_btn)
        
        apply_btn = QPushButton("[APPLY] Apply Template")
        apply_btn.clicked.connect(lambda: self.apply_template(dialog, templates_list))
        template_buttons.addWidget(apply_btn)
        
        delete_btn = QPushButton("[DELETE] Delete")
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
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Search input
        search_layout = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Enter search query...")
        search_layout.addWidget(search_input)
        
        search_btn = QPushButton("[SEARCH] Search")
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

