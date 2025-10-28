# AWG-Kumulus Desktop Application

A comprehensive desktop application for firmware management, device detection, and automated reporting.

## 📚 Documentation

All documentation is organized in the [`docs/`](docs/) folder:

- **[📖 Documentation Index](docs/README.md)** - Complete documentation overview
- **[🚀 Quick Start](docs/guides/QUICKSTART.md)** - Get started quickly
- **[🔌 Firmware Guide](docs/guides/FIRMWARE_GUIDE.md)** - Firmware management
- **[⚙️ Pipeline Setup](docs/guides/PIPELINE_SETUP_GUIDE.md)** - CI/CD configuration
- **[📧 Email Features](docs/features/AUTO_EMAIL_FEATURE.md)** - Automated reporting
- **[💡 Examples](docs/examples/README.md)** - Practical examples

## 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**
   ```bash
   python main.py
   ```

3. **Configure**
   - Copy `config.example.json` to your config
   - Set up email and OneDrive credentials
   - Configure machine types

## 🔧 Features

- **Multi-platform Support**: Windows, macOS, Linux
- **Device Detection**: ESP32, STM32, Arduino boards
- **Firmware Management**: Local, GitHub, GitLab sources
- **Automated Reporting**: Email and OneDrive integration
- **Version Control**: Firmware versioning and rollback
- **CI/CD Integration**: GitHub Actions and GitLab pipelines

## 📁 Project Structure

```
├── docs/                    # Complete documentation
├── src/                     # Source code
│   ├── core/               # Core functionality
│   └── gui/                # User interface
├── tests/                  # Test suite
├── config.example.json     # Example configuration
├── requirements.txt        # Python dependencies
└── main.py                 # Application entry point
```

## 🤝 Contributing

1. Read the [Documentation](docs/README.md)
2. Check the [Architecture](docs/ARCHITECTURE.md)
3. Review [Examples](docs/examples/README.md)
4. Submit pull requests

## 📞 Support

- **Documentation**: [docs/README.md](docs/README.md)
- **Issues**: Use the project's issue tracker
- **Examples**: [docs/examples/](docs/examples/)

---

**Version**: 1.0.0  
**License**: See LICENSE file  
**Maintainer**: AWG-Kumulus Development Team
