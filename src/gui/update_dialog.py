import os
import sys
import tempfile
import subprocess
import requests
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTextBrowser, 
    QHBoxLayout, QProgressBar, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QCoreApplication, QUrl
from PySide6.QtGui import QDesktopServices, QIcon

class DownloadWorker(QThread):
    progress = Signal(int)
    finished = Signal(str) # path to file
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self._is_running = True

    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            # Create temp file
            fd, path = tempfile.mkstemp(suffix=".exe")
            os.close(fd)
            
            downloaded = 0
            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self._is_running:
                        f.close()
                        os.remove(path)
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.progress.emit(percent)
            
            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._is_running = False

class UpdateCheckWorker(QThread):
    finished = Signal(object)

    def __init__(self, updater, current_version):
        super().__init__()
        self.updater = updater
        self.current_version = current_version

    def run(self):
        result = self.updater.check_for_updates(self.current_version)
        self.finished.emit(result)

class UpdateDialog(QDialog):
    def __init__(self, parent=None, updater=None, current_version="0.0.0", cached_result=None):
        super().__init__(parent)
        self.updater = updater
        self.current_version = current_version
        self.update_info = None
        self.download_worker = None
        
        self.setWindowTitle(QCoreApplication.translate("UpdateDialog", "Check for Updates"))
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        
        layout = QVBoxLayout(self)
        
        # Status Icon & Label
        self.status_label = QLabel(QCoreApplication.translate("UpdateDialog", "Checking for updates..."))
        self.status_label.setAlignment(Qt.AlignCenter)
        font = self.status_label.font()
        font.setPointSize(10)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0) # Indeterminate
        layout.addWidget(self.progress)
        
        # Release Notes
        self.notes_browser = QTextBrowser()
        self.notes_browser.setVisible(False)
        layout.addWidget(self.notes_browser)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.download_btn = QPushButton(QCoreApplication.translate("UpdateDialog", "Install Update"))
        self.download_btn.clicked.connect(self.download_update)
        self.download_btn.setVisible(False)
        # Apply primary style manually if needed, or rely on parent theme
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #93c5fd;
            }
        """)
        button_layout.addWidget(self.download_btn)
        
        self.close_btn = QPushButton(QCoreApplication.translate("UpdateDialog", "Close"))
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        # Start check or use cached result
        if cached_result:
            self.on_check_finished(cached_result)
        else:
            self.start_check()

    def start_check(self):
        self.worker = UpdateCheckWorker(self.updater, self.current_version)
        self.worker.finished.connect(self.on_check_finished)
        self.worker.start()

    def on_check_finished(self, result):
        self.progress.setVisible(False)
        self.update_info = result
        
        if result:
            new_version = result.get('version', 'unknown')
            self.status_label.setText(
                QCoreApplication.translate("UpdateDialog", "New version available: {}").format(new_version)
            )
            self.notes_browser.setMarkdown(result.get('notes', ''))
            self.notes_browser.setVisible(True)
            self.download_btn.setVisible(True)
            self.setWindowTitle(QCoreApplication.translate("UpdateDialog", "Update Available"))
            
            # If we have a direct download URL, enable install
            if not result.get('download_url'):
                self.download_btn.setText(QCoreApplication.translate("UpdateDialog", "Download Page"))
        else:
            self.status_label.setText(QCoreApplication.translate("UpdateDialog", "You are using the latest version."))
            self.setWindowTitle(QCoreApplication.translate("UpdateDialog", "No Updates"))

    def download_update(self):
        if not self.update_info:
            return

        download_url = self.update_info.get('download_url')
        if not download_url:
            # Fallback to opening browser
            if 'url' in self.update_info:
                QDesktopServices.openUrl(QUrl(self.update_info['url']))
                self.close()
            return

        # Start download
        self.download_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.status_label.setText(QCoreApplication.translate("UpdateDialog", "Downloading update..."))
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        
        self.download_worker = DownloadWorker(download_url)
        self.download_worker.progress.connect(self.progress.setValue)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.error.connect(self.on_download_error)
        self.download_worker.start()

    def on_download_finished(self, path):
        self.status_label.setText(QCoreApplication.translate("UpdateDialog", "Installing..."))
        try:
            # Run the installer
            subprocess.Popen([path], shell=True)
            # Quit this app
            QCoreApplication.quit()
        except Exception as e:
            self.on_download_error(str(e))

    def on_download_error(self, error_msg):
        self.download_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.status_label.setText(QCoreApplication.translate("UpdateDialog", "Download failed"))
        QMessageBox.critical(self, "Update Error", f"Failed to download update:\n{error_msg}")

    def closeEvent(self, event):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.stop()
            self.download_worker.wait()
        super().closeEvent(event)
