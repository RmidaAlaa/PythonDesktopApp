"""Setup script for AWG Kumulus Device Manager."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="awg-kumulus-device-manager",
    version="1.0.0",
    author="AWG",
    description="Cross-platform device manager for embedded boards",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/awg/kumulus-device-manager",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries",
    ],
    python_requires=">=3.11",
    install_requires=[
        "PySide6>=6.5.0",
        "pyserial>=3.5",
        "pyusb>=1.2.1",
        "openpyxl>=3.1.2",
        "requests>=2.31.0",
        "keyring>=24.2.0",
        "tqdm>=4.66.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-mock>=3.11.0",
            "pyinstaller>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "awg-kumulus=main:main",
        ],
    },
    package_data={
        "": ["*.json"],
    },
)

