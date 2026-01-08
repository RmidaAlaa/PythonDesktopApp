#!/bin/bash
# Build script for macOS
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Building executable..."
pyinstaller build_macos.spec

echo "Build complete. Output in dist/"
