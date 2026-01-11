#!/usr/bin/env python3
"""
Build script for AWG Kumulus Device Manager.
Usage: python build.py [windows|linux|macos|all]
"""

import sys
import platform
import subprocess
import argparse
import re
from pathlib import Path


def increment_version():
    """Increment the application patch version."""
    version_file = Path("src/core/version.py")
    config_file = Path("src/core/config.py")
    
    if not version_file.exists():
        print("Warning: src/core/version.py not found. Skipping version increment.")
        return "0.0.0"

    # Read version.py
    content = version_file.read_text(encoding="utf-8")
    
    # Find current version
    # Matches: version = os.environ.get("APP_VERSION", "1.0.0")
    match = re.search(r'os\.environ\.get\("APP_VERSION", "(\d+)\.(\d+)\.(\d+)"\)', content)
    
    if not match:
        print("Warning: Could not find version pattern in src/core/version.py")
        return "0.0.0"
        
    major, minor, patch = map(int, match.groups())
    new_patch = patch + 1
    new_version = f"{major}.{minor}.{new_patch}"
    
    print(f"Incrementing version: {major}.{minor}.{patch} -> {new_version}")
    
    # Update version.py
    new_content = re.sub(
        r'os\.environ\.get\("APP_VERSION", "\d+\.\d+\.\d+"\)',
        f'os.environ.get("APP_VERSION", "{new_version}")',
        content
    )
    version_file.write_text(new_content, encoding="utf-8")
    
    # Update config.py if it exists
    if config_file.exists():
        config_content = config_file.read_text(encoding="utf-8")
        # Matches: "version": "1.0.0",
        config_match = re.search(r'"version": "\d+\.\d+\.\d+"', config_content)
        if config_match:
            new_config_content = re.sub(
                r'"version": "\d+\.\d+\.\d+"',
                f'"version": "{new_version}"',
                config_content
            )
            config_file.write_text(new_config_content, encoding="utf-8")
            print("Updated version in src/core/config.py")
            
    return new_version


def build_windows():
    """Build for Windows."""
    print("Building for Windows...")
    subprocess.run(["pyinstaller", "build_windows.spec"], check=True)
    print("✓ Windows build complete")
    print("  Output: dist/AWG-Kumulus-Device-Manager.exe")


def build_linux():
    """Build for Linux."""
    print("Building for Linux...")
    subprocess.run(["pyinstaller", "build_linux.spec"], check=True)
    print("✓ Linux build complete")
    print("  Output: dist/AWG-Kumulus-Device-Manager/")


def build_macos():
    """Build for macOS."""
    print("Building for macOS...")
    subprocess.run(["pyinstaller", "build_macos.spec"], check=True)
    print("✓ macOS build complete")
    print("  Output: dist/AWG-Kumulus-Device-Manager.app")


def main():
    """Main build function."""
    parser = argparse.ArgumentParser(description="Build AWG Kumulus Device Manager")
    parser.add_argument(
        "platform",
        nargs="?",
        choices=["windows", "linux", "macos", "all", "native"],
        default="native",
        help="Platform to build for"
    )
    
    args = parser.parse_args()
    
    # Determine platform
    target_platform = args.platform
    if target_platform == "native":
        system = platform.system().lower()
        if system == "windows":
            target_platform = "windows"
        elif system == "darwin":
            target_platform = "macos"
        else:
            target_platform = "linux"
    
    print(f"Building for: {target_platform}")
    print("-" * 50)
    
    # Increment version before build
    new_version = increment_version()
    print(f"Target Version: {new_version}")
    print("-" * 50)
    
    try:
        if target_platform == "windows":
            build_windows()
        elif target_platform == "linux":
            build_linux()
        elif target_platform == "macos":
            build_macos()
        elif target_platform == "all":
            build_windows()
            build_linux()
            build_macos()
        
        print("-" * 50)
        print("✓ Build completed successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Build failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n✗ Build interrupted")
        sys.exit(1)


if __name__ == "__main__":
    main()

