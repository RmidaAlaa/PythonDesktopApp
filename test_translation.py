#!/usr/bin/env python3
"""
Test file for pylupdate detection.
"""

from PySide6.QtCore import QCoreApplication

def tr(context, text):
    """Translation function."""
    return QCoreApplication.translate(context, text)

# Test translatable strings
test_string = tr("TestContext", "Hello World")
button_text = tr("TestContext", "Click Me")
window_title = tr("TestContext", "Test Window")
