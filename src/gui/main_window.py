"""Main application window."""

import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QProgressBar, QMessageBox,
    QGroupBox, QSplitter, QApplication, QHeaderView, QDialog,
    QDialogButtonBox
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

logger = setup_logger("MainWindow")


class WorkerThread(QThread):
    """Worker thread for background operations."""
    finished = Signal()
    error = Signal(str)
    
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
        self.last_report_path = None  # Store last generated report path
        self.setup_ui()
        
        # Initialize components
        self.device_detector = DeviceDetector()
        self.report_generator = ReportGenerator()
        self.email_sender = EmailSender()
        self.firmware_flasher = FirmwareFlasher()
        
        # Auto-detect devices on startup
        QTimer.singleShot(500, self.refresh_devices)
        
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
        self.device_table.setColumnCount(5)
        self.device_table.setHorizontalHeaderLabels([
            "Port", "Type", "VID:PID", "Status", "Action"
        ])
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.device_table)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Devices")
        refresh_btn.clicked.connect(self.refresh_devices)
        layout.addWidget(refresh_btn)
        
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
        self.machine_type.addItems(list(Config.MACHINE_TYPES.keys()))
        machine_type_idx = list(Config.MACHINE_TYPES.keys()).index(
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
        
        export_btn = QPushButton("📊 Generate Excel Report")
        export_btn.clicked.connect(self.generate_report)
        button_layout.addWidget(export_btn)
        
        email_btn = QPushButton("📧 Send Email")
        email_btn.clicked.connect(self.send_email)
        button_layout.addWidget(email_btn)
        
        flash_btn = QPushButton("⚡ Flash Firmware")
        flash_btn.clicked.connect(self.flash_firmware_dialog)
        button_layout.addWidget(flash_btn)
        
        layout.addLayout(button_layout)
        
        # Settings button
        settings_btn = QPushButton("⚙️ Configure Email")
        settings_btn.clicked.connect(self.configure_email_dialog)
        layout.addWidget(settings_btn)
        
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
            self.device_table.setItem(row, 0, QTableWidgetItem(device.port))
            self.device_table.setItem(row, 1, QTableWidgetItem(device.board_type.value))
            
            vid_pid = f"{device.vid:04X}:{device.pid:04X}" if device.vid and device.pid else "N/A"
            self.device_table.setItem(row, 2, QTableWidgetItem(vid_pid))
            self.device_table.setItem(row, 3, QTableWidgetItem("Connected"))
            
            # Action button
            btn = QPushButton("Select")
            btn.clicked.connect(lambda checked, d=device: self.select_device(d))
            self.device_table.setCellWidget(row, 4, btn)
    
    def select_device(self, device: Device):
        """Handle device selection."""
        self.log(f"Selected device: {device.port} ({device.board_type.value})")
        self.statusBar().showMessage(f"Selected: {device.port}")
    
    def on_machine_type_changed(self, text):
        """Handle machine type change."""
        # Reset machine ID placeholder with prefix
        prefix = Config.MACHINE_TYPES[text]['prefix']
        self.machine_id.setPlaceholderText(f"e.g., {prefix}XXXXX")
    
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
            type_config = Config.MACHINE_TYPES[machine_type]
            prefix = type_config['prefix']
            expected_length = type_config['length']
            
            if not machine_id.startswith(prefix) or len(machine_id) != expected_length:
                QMessageBox.warning(self, "Validation Error",
                                  f"Machine ID must start with '{prefix}' and have {expected_length} characters")
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
            
            email_body = f"""AWG Kumulus Device Manager Report

Operator: {operator_name} ({operator_email})
Machine Type: {machine_type}
Machine ID: {machine_id}
Devices Detected: {len(self.devices)}

Please find the attached Excel report with device details."""
            
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
    
    def configure_email_dialog(self):
        """Open email configuration dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Email Configuration")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # SMTP Server
        layout.addWidget(QLabel("SMTP Server:"))
        smtp_host = QLineEdit()
        smtp_host.setText(self.config.get('smtp', {}).get('host', ''))
        smtp_host.setPlaceholderText("e.g., smtp.gmail.com")
        layout.addWidget(smtp_host)
        
        # Port
        layout.addWidget(QLabel("Port:"))
        smtp_port = QLineEdit()
        smtp_port.setText(str(self.config.get('smtp', {}).get('port', 587)))
        layout.addWidget(smtp_port)
        
        # Username
        layout.addWidget(QLabel("Email Username:"))
        smtp_user = QLineEdit()
        smtp_user.setText(self.config.get('smtp', {}).get('username', ''))
        layout.addWidget(smtp_user)
        
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
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec():
            # Save configuration
            self.config['smtp'] = {
                'host': smtp_host.text(),
                'port': int(smtp_port.text() or 587),
                'tls': True,
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
        
        # Simplified - would open a proper dialog
        QMessageBox.information(self, "Flash Firmware",
                                "Firmware flashing dialog would open here.")
    
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

