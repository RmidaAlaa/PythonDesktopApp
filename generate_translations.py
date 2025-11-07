#!/usr/bin/env python3
"""
Translation file generation script.
Generates `.ts` files (pylupdate6) and compiles to `.qm` (lrelease).

Robust tool discovery on Windows:
- Searches PATH for `pylupdate6` / `lrelease`
- Checks common site-packages locations for PyQt6/pyqt6-tools
- Uses env var `QT_BIN` when set (expects `lrelease.exe` inside)
"""

import subprocess
import sys
from pathlib import Path
import os
import glob

def _which(cmd):
    """Return cmd if it seems available. Try common version flags, or path existence for .exe."""
    try:
        for flag in ("--version", "-version"):
            try:
                res = subprocess.run([cmd, flag], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return cmd
            except Exception:
                pass
        # If it's an absolute path to an exe, accept existence.
        if cmd.lower().endswith(".exe") and Path(cmd).exists():
            return cmd
    except Exception:
        pass
    return None

def find_pylupdate():
    """Find pylupdate executable (prefer version 6)."""
    # Try PATH first
    for name in ("pylupdate6", "pylupdate5", "pylupdate"):
        found = _which(name)
        if found:
            print(f"Found {name} on PATH: {found}")
            return found

    # Try common Scripts directories
    scripts_patterns = [
        r"C:\\Users\\*\\AppData\\Local\\Programs\\Python\\Python*\\Scripts\\pylupdate6.exe",
        r"C:\\Python*\\Scripts\\pylupdate6.exe",
        r"C:\\Users\\*\\AppData\\Local\\Programs\\Python\\Python*\\Scripts\\pylupdate5.exe",
    ]
    for pattern in scripts_patterns:
        for p in glob.glob(pattern):
            if _which(p):
                print(f"Found pylupdate at: {p}")
                return p

    # Try site-packages for pyqt tools
    site_packages = [sys.prefix, sys.base_prefix]
    candidates = []
    for root in site_packages:
        candidates += glob.glob(os.path.join(root, "Lib", "site-packages", "PyQt6*", "Qt*", "bin", "pylupdate6.exe"))
        candidates += glob.glob(os.path.join(root, "Lib", "site-packages", "PySide6*", "Qt*", "bin", "pylupdate6.exe"))
    for p in candidates:
        if _which(p):
            print(f"Found pylupdate at: {p}")
            return p

    return None

def generate_translation_files():
    """Generate translation files using pylupdate."""
    pylupdate_path = find_pylupdate()
    if not pylupdate_path:
        print("Error: pylupdate not found. Please install PyQt6 or PyQt5 tools.")
        print("You can install it with: pip install PyQt6-tools")
        return False
    
    # Get project root directory
    project_root = Path(__file__).parent
    src_dir = project_root / "src"
    translations_dir = project_root / "translations"
    
    # Create translations directory
    translations_dir.mkdir(exist_ok=True)
    
    # Find all Python files in src directory
    python_files = []
    for py_file in src_dir.rglob("*.py"):
        python_files.append(str(py_file))
    
    if not python_files:
        print("No Python files found in src directory")
        return False
    
    print(f"Found {len(python_files)} Python files")
    
    # Languages to generate translations for
    languages = ["fr"]  # French only (English is the source language)
    
    success = True
    
    for lang in languages:
        ts_file = translations_dir / f"app_{lang}.ts"
        
        print(f"Generating translation file for {lang}: {ts_file}")
        
        try:
            # Run pylupdate
            cmd = [
                pylupdate_path,
                "--ts", str(ts_file),
                "--verbose"
            ] + python_files
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print(f"[OK] Successfully generated {ts_file}")
                
                # Check if file was created and has content
                if ts_file.exists() and ts_file.stat().st_size > 100:
                    print(f"  File size: {ts_file.stat().st_size} bytes")
                else:
                    print(f"  Warning: File seems empty or very small")
                    
            else:
                print(f"[ERROR] Failed to generate {ts_file}")
                print(f"Error: {result.stderr}")
                success = False
                
        except subprocess.TimeoutExpired:
            print(f"[ERROR] Timeout generating {ts_file}")
            success = False
        except Exception as e:
            print(f"[ERROR] Error generating {ts_file}: {e}")
            success = False
    
    return success

def compile_translations():
    """Compile .ts files to .qm files using lrelease (try multiple discovery strategies)."""
    translations_dir = Path(__file__).parent / "translations"
    if not translations_dir.exists():
        print("No translations directory found")
        return False

    # Discovery order: PATH -> QT_BIN -> Scripts -> site-packages
    lrelease_path = None

    for name in ("lrelease6", "lrelease", "lrelease5"):
        lrelease_path = _which(name)
        if lrelease_path:
            print(f"Found {name} on PATH: {lrelease_path}")
            break

    if not lrelease_path:
        qt_bin = os.environ.get("QT_BIN")
        if qt_bin:
            candidate = os.path.join(qt_bin, "lrelease.exe")
            if _which(candidate):
                lrelease_path = candidate
                print(f"Found lrelease via QT_BIN: {lrelease_path}")

    if not lrelease_path:
        for pattern in (
            r"C:\\Users\\*\\AppData\\Local\\Programs\\Python\\Python*\\Scripts\\lrelease.exe",
            r"C:\\Python*\\Scripts\\lrelease.exe",
        ):
            for p in glob.glob(pattern):
                if _which(p):
                    lrelease_path = p
                    print(f"Found lrelease at: {p}")
                    break
            if lrelease_path:
                break

    if not lrelease_path:
        site_packages = [sys.prefix, sys.base_prefix]
        candidates = []
        for root in site_packages:
            candidates += glob.glob(os.path.join(root, "Lib", "site-packages", "PyQt6*", "Qt*", "bin", "lrelease.exe"))
            candidates += glob.glob(os.path.join(root, "Lib", "site-packages", "PySide6*", "Qt*", "bin", "lrelease.exe"))
            candidates += glob.glob(os.path.join(root, "Lib", "site-packages", "pyqt6_tools*", "Qt*", "bin", "lrelease.exe"))
            candidates += glob.glob(os.path.join(root, "Lib", "site-packages", "qt6_applications*", "Qt", "bin", "lrelease.exe"))
        for p in candidates:
            if _which(p):
                lrelease_path = p
                print(f"Found lrelease at: {p}")
                break

    if not lrelease_path:
        print("Warning: lrelease not found. .ts generated but not compiled to .qm.")
        print("Install Qt or set QT_BIN to the Qt bin directory containing lrelease.exe")
        return True

    success = True
    for ts_file in translations_dir.glob("*.ts"):
        qm_file = ts_file.with_suffix(".qm")
        print(f"Compiling {ts_file} -> {qm_file}")
        try:
            result = subprocess.run([lrelease_path, str(ts_file)], capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and qm_file.exists():
                print(f"[OK] {qm_file}")
            else:
                print(f"[ERROR] Failed to compile {ts_file}")
                print(result.stdout)
                print(result.stderr)
                success = False
        except Exception as e:
            print(f"[ERROR] Error compiling {ts_file}: {e}")
            success = False
    return success

def main():
    """Main function."""
    print("=== Translation File Generator ===")
    print()
    
    # Generate .ts files
    print("Step 1: Generating translation source files (.ts)")
    if not generate_translation_files():
        print("Failed to generate translation files")
        return 1
    
    print()
    
    # Compile to .qm files
    print("Step 2: Compiling translation files (.qm)")
    if not compile_translations():
        print("Failed to compile translation files")
        return 1
    
    print()
    print("=== Translation files generated successfully! ===")
    print()
    print("Next steps:")
    print("1. Edit the .ts files in the translations/ directory")
    print("2. Add translations for your target languages")
    print("3. Re-run this script to compile updated translations")
    print("4. The application will automatically load the .qm files")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
