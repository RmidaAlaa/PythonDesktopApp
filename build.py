#!/usr/bin/env python3
"""
Build script for AWG Kumulus Device Manager.
Usage: python build.py [windows|linux|macos|all]
"""

import sys
import platform
import subprocess
import argparse


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

