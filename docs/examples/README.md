# AWG-Kumulus Desktop Application Examples

This directory contains practical examples and code snippets for using the AWG-Kumulus Desktop Application.

## 📁 Examples Structure

```
examples/
├── README.md                    # This file
├── firmware/                    # Firmware management examples
│   ├── basic_flashing.py        # Basic firmware flashing
│   ├── github_integration.py    # GitHub release integration
│   ├── gitlab_integration.py    # GitLab pipeline integration
│   └── batch_operations.py      # Batch firmware operations
├── device_detection/            # Device detection examples
│   ├── scan_devices.py          # Device scanning
│   ├── filter_devices.py        # Device filtering
│   └── device_info.py           # Device information retrieval
├── email_reports/               # Email reporting examples
│   ├── basic_email.py           # Basic email sending
│   ├── report_generation.py     # Report generation
│   └── scheduled_reports.py     # Scheduled reporting
├── onedrive/                    # OneDrive integration examples
│   ├── upload_files.py          # File upload
│   ├── sync_folders.py          # Folder synchronization
│   └── backup_reports.py        # Report backup
└── configuration/               # Configuration examples
    ├── custom_config.py         # Custom configuration
    ├── machine_types.py         # Machine type setup
    └── environment_setup.py     # Environment configuration
```

## 🚀 Quick Start Examples

### Basic Firmware Flashing
```python
from src.core.firmware_flasher import FirmwareFlasher
from src.core.device_detector import DeviceDetector

# Initialize components
flasher = FirmwareFlasher()
detector = DeviceDetector()

# Detect devices
devices = detector.detect_devices()
if devices:
    device = devices[0]
    
    # Flash firmware
    success = flasher.flash_firmware(
        device=device,
        firmware_source="/path/to/firmware.bin"
    )
    
    print(f"Flashing {'successful' if success else 'failed'}")
```

### Device Detection
```python
from src.core.device_detector import DeviceDetector, BoardType

detector = DeviceDetector()
devices = detector.detect_devices()

# Filter by board type
esp32_devices = [d for d in devices if d.board_type == BoardType.ESP32]
stm32_devices = [d for d in devices if d.board_type == BoardType.STM32]

print(f"Found {len(esp32_devices)} ESP32 devices")
print(f"Found {len(stm32_devices)} STM32 devices")
```

### Email Reporting
```python
from src.core.email_sender import EmailSender
from src.core.report_generator import ReportGenerator

# Generate report
report_gen = ReportGenerator()
report_data = report_gen.generate_report()

# Send email
email_sender = EmailSender()
success = email_sender.send_report(
    recipients=["admin@example.com"],
    report_data=report_data
)

print(f"Email {'sent' if success else 'failed'}")
```

## 📚 Detailed Examples

### 1. Firmware Management Examples

#### Basic Firmware Flashing
See `firmware/basic_flashing.py` for a complete example of:
- Device detection
- Firmware validation
- Progress callbacks
- Error handling

#### GitHub Integration
See `firmware/github_integration.py` for:
- Adding firmware from GitHub releases
- Automatic version checking
- Release management

#### GitLab Integration
See `firmware/gitlab_integration.py` for:
- GitLab pipeline integration
- Artifact management
- Project configuration

#### Batch Operations
See `firmware/batch_operations.py` for:
- Multiple device flashing
- Parallel operations
- Progress tracking

### 2. Device Detection Examples

#### Device Scanning
See `device_detection/scan_devices.py` for:
- Comprehensive device scanning
- Board type detection
- Port enumeration

#### Device Filtering
See `device_detection/filter_devices.py` for:
- Filtering by board type
- Filtering by port
- Custom device criteria

#### Device Information
See `device_detection/device_info.py` for:
- Detailed device information
- Firmware version detection
- Hardware specifications

### 3. Email Reporting Examples

#### Basic Email
See `email_reports/basic_email.py` for:
- Simple email sending
- Attachment handling
- SMTP configuration

#### Report Generation
See `email_reports/report_generation.py` for:
- Automated report creation
- Data formatting
- Template usage

#### Scheduled Reports
See `email_reports/scheduled_reports.py` for:
- Automated scheduling
- Cron-like functionality
- Error handling

### 4. OneDrive Integration Examples

#### File Upload
See `onedrive/upload_files.py` for:
- File upload to OneDrive
- Progress tracking
- Error handling

#### Folder Sync
See `onedrive/sync_folders.py` for:
- Folder synchronization
- Conflict resolution
- Change detection

#### Report Backup
See `onedrive/backup_reports.py` for:
- Automated report backup
- Version management
- Retention policies

### 5. Configuration Examples

#### Custom Configuration
See `configuration/custom_config.py` for:
- Custom configuration setup
- Environment variables
- Validation

#### Machine Types
See `configuration/machine_types.py` for:
- Machine type configuration
- Validation rules
- Custom types

#### Environment Setup
See `configuration/environment_setup.py` for:
- Development environment
- Production setup
- Testing configuration

## 🔧 Running Examples

### Prerequisites
1. Install the application dependencies
2. Configure the application (see configuration examples)
3. Set up required services (email, OneDrive, etc.)

### Running Individual Examples
```bash
# Run a specific example
python examples/firmware/basic_flashing.py

# Run with custom configuration
python examples/firmware/github_integration.py --config custom_config.json

# Run with verbose output
python examples/device_detection/scan_devices.py --verbose
```

### Running All Examples
```bash
# Run all examples (if available)
python examples/run_all_examples.py

# Run examples by category
python examples/run_firmware_examples.py
python examples/run_email_examples.py
```

## 📝 Example Customization

### Modifying Examples
1. Copy the example file
2. Modify the configuration
3. Adjust the parameters
4. Test with your setup

### Creating New Examples
1. Follow the existing structure
2. Include proper error handling
3. Add documentation
4. Test thoroughly

## 🐛 Troubleshooting Examples

### Common Issues
- **Import Errors**: Ensure the application is properly installed
- **Configuration Issues**: Check configuration files
- **Permission Errors**: Verify file and device permissions
- **Network Issues**: Check internet connectivity

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Your example code here
```

## 📞 Support

For issues with examples:
1. Check the troubleshooting section
2. Review the main documentation
3. Check the project's issue tracker
4. Contact the development team

---

**Note**: These examples are provided as-is and may require modification for your specific use case. Always test in a safe environment before using in production.
