#!/bin/bash
# Build script for Linux
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Building executable..."
pyinstaller build_linux.spec

echo "Build complete. Output in dist/"
