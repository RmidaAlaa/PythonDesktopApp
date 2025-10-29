#!/usr/bin/env python3
"""
Translation file generation script using pylupdate.
Generates .ts files for translation and .qm files for runtime.
"""

import subprocess
import sys
from pathlib import Path
import os

def find_pylupdate():
    """Find pylupdate executable."""
    # Common locations for pylupdate
    possible_paths = [
        "pylupdate6",
        "pylupdate5", 
        "pylupdate",
        "C:/Python*/Scripts/pylupdate6.exe",
        "C:/Python*/Scripts/pylupdate5.exe",
    ]
    
    for path in possible_paths:
        try:
            result = subprocess.run([path, "--version"], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"Found pylupdate at: {path}")
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            continue
    
    return None

def generate_translation_files():
    """Generate translation files using pylupdate."""
    pylupdate_path = find_pylupdate()
    if not pylupdate_path:
        print("Error: pylupdate not found. Please install PyQt6 or PyQt5 tools.")
        print("You can install it with: pip install PyQt6-tools")
        return False
    
    # Get project root directory
    project_root = Path(__file__).parent.parent
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
    languages = ["ar", "fr"]  # Arabic and French
    
    success = True
    
    for lang in languages:
        ts_file = translations_dir / f"app_{lang}.ts"
        
        print(f"Generating translation file for {lang}: {ts_file}")
        
        try:
            # Run pylupdate
            cmd = [
                pylupdate_path,
                "-ts", str(ts_file),
                "-verbose"
            ] + python_files
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print(f"✓ Successfully generated {ts_file}")
                
                # Check if file was created and has content
                if ts_file.exists() and ts_file.stat().st_size > 100:
                    print(f"  File size: {ts_file.stat().st_size} bytes")
                else:
                    print(f"  Warning: File seems empty or very small")
                    
            else:
                print(f"✗ Failed to generate {ts_file}")
                print(f"Error: {result.stderr}")
                success = False
                
        except subprocess.TimeoutExpired:
            print(f"✗ Timeout generating {ts_file}")
            success = False
        except Exception as e:
            print(f"✗ Error generating {ts_file}: {e}")
            success = False
    
    return success

def compile_translations():
    """Compile .ts files to .qm files using lrelease."""
    translations_dir = Path(__file__).parent.parent / "translations"
    
    if not translations_dir.exists():
        print("No translations directory found")
        return False
    
    # Find lrelease
    lrelease_paths = [
        "lrelease6",
        "lrelease5",
        "lrelease",
        "C:/Python*/Scripts/lrelease6.exe",
        "C:/Python*/Scripts/lrelease5.exe",
    ]
    
    lrelease_path = None
    for path in lrelease_paths:
        try:
            result = subprocess.run([path, "--version"], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lrelease_path = path
                break
        except:
            continue
    
    if not lrelease_path:
        print("Warning: lrelease not found. Translation files (.ts) generated but not compiled to .qm")
        print("You can manually compile them later or install Qt tools")
        return True
    
    print(f"Found lrelease at: {lrelease_path}")
    
    success = True
    for ts_file in translations_dir.glob("*.ts"):
        qm_file = ts_file.with_suffix(".qm")
        
        print(f"Compiling {ts_file} to {qm_file}")
        
        try:
            result = subprocess.run([lrelease_path, str(ts_file)], 
                                 capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and qm_file.exists():
                print(f"✓ Successfully compiled {qm_file}")
            else:
                print(f"✗ Failed to compile {ts_file}")
                print(f"Error: {result.stderr}")
                success = False
                
        except Exception as e:
            print(f"✗ Error compiling {ts_file}: {e}")
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
