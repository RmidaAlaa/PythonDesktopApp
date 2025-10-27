#!/usr/bin/env python3
"""Display project structure in a tree format."""

from pathlib import Path
import os


def print_tree(directory, prefix="", is_last=True):
    """Print directory tree."""
    directory = Path(directory)
    
    # Get base name
    name = directory.name if directory.is_dir() else directory.name
    
    # Print current item
    connector = "└── " if is_last else "├── "
    print(f"{prefix}{connector}{name}")
    
    if directory.is_dir():
        # Get items
        items = sorted(directory.iterdir())
        for i, item in enumerate(items):
            is_last_item = i == len(items) - 1
            extension = "    " if is_last else "│   "
            print_tree(item, prefix + extension, is_last_item)


def main():
    """Main function."""
    print("AWG Kumulus Device Manager - Project Structure")
    print("=" * 50)
    print()
    
    # Get current directory
    current_dir = Path(".")
    
    # Print tree
    print_tree(current_dir, is_last=True)
    
    print()
    print("=" * 50)
    print("Total files: ", sum(1 for _ in Path(".").rglob("*.*") if _.is_file()))
    print("Total lines of code: ", sum(
        p.stat().st_size for p in Path("src").rglob("*.py")
    ))


if __name__ == "__main__":
    main()

