#!/usr/bin/env python3
"""
Test file for pylupdate detection with direct tr calls.
"""

from PySide6.QtCore import QCoreApplication

def tr(context, text):
    """Translation function."""
    return QCoreApplication.translate(context, text)

# Direct tr calls without f-strings
window_title = tr("MainWindow", "AWG Kumulus Device Manager v1.0.0")
refresh_text = tr("MainWindow", "Refresh Devices")
port_text = tr("MainWindow", "Port")
status_text = tr("MainWindow", "Status")
health_text = tr("MainWindow", "Health")
name_text = tr("MainWindow", "Name")
last_seen_text = tr("MainWindow", "Last Seen")
action_text = tr("MainWindow", "Action")
