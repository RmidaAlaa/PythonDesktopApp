# GitHub and GitLab Pipeline Setup Guide for Firmware Management

## Table of Contents
1. [Overview](#overview)
2. [GitHub Actions Setup](#github-actions-setup)
3. [GitLab CI/CD Setup](#gitlab-cicd-setup)
4. [Firmware Build Workflows](#firmware-build-workflows)
5. [Release Management](#release-management)
6. [Integration with Desktop App](#integration-with-desktop-app)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Overview

This guide covers setting up automated firmware builds and releases using GitHub Actions and GitLab CI/CD pipelines. These pipelines will automatically build firmware for different board types and make them available for the AWG-Kumulus Desktop Application.

### Benefits of Automated Pipelines
- **Consistent Builds**: Same build environment every time
- **Multi-platform Support**: Build for different architectures
- **Automatic Releases**: Tagged releases trigger firmware builds
- **Version Management**: Automatic versioning and changelog generation
- **Quality Assurance**: Automated testing and validation
- **Easy Distribution**: Direct integration with desktop application

## GitHub Actions Setup

### 1. Repository Structure

Organize your firmware project with the following structure:

```
firmware-project/
├── .github/
│   └── workflows/
│       ├── build-firmware.yml
│       ├── release.yml
│       └── test.yml
├── src/
│   ├── esp32/
│   ├── stm32/
│   └── arduino/
├── docs/
├── tests/
├── CMakeLists.txt
├── platformio.ini
└── README.md
```

### 2. Basic Firmware Build Workflow

Create `.github/workflows/build-firmware.yml`:

```yaml
name: Build Firmware

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build-esp32:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        board: [esp32, esp32-s2, esp32-s3]
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      with:
        submodules: recursive
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install ESP-IDF
      uses: espressif/esp-idf-ci-action@v1
      with:
        esp_idf_version: 'v4.4'
    
    - name: Build firmware
      run: |
        idf.py set-target ${{ matrix.board }}
        idf.py build
    
    - name: Upload build artifacts
      uses: actions/upload-artifact@v3
      with:
        name: firmware-${{ matrix.board }}
        path: build/*.bin
        retention-days: 30

  build-stm32:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        board: [stm32f4, stm32f7, stm32h7]
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up ARM toolchain
      run: |
        sudo apt-get update
        sudo apt-get install -y gcc-arm-none-eabi
    
    - name: Build STM32 firmware
      run: |
        make BOARD=${{ matrix.board }} clean
        make BOARD=${{ matrix.board }} all
    
    - name: Upload build artifacts
      uses: actions/upload-artifact@v3
      with:
        name: firmware-${{ matrix.board }}
        path: build/*.bin
        retention-days: 30

  build-arduino:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        board: [arduino_uno, arduino_nano, arduino_mega]
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up PlatformIO
      uses: platformio/platformio-core-action@v1
      with:
        platform: atmelavr
    
    - name: Build Arduino firmware
      run: |
        pio run -e ${{ matrix.board }}
    
    - name: Upload build artifacts
      uses: actions/upload-artifact@v3
      with:
        name: firmware-${{ matrix.board }}
        path: .pio/build/*/firmware.hex
        retention-days: 30
```

### 3. Release Workflow

Create `.github/workflows/release.yml`:

```yaml
name: Create Release

on:
  push:
    tags:
      - 'v*'

jobs:
  create-release:
    runs-on: ubuntu-latest
    needs: [build-esp32, build-stm32, build-arduino]
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Download all artifacts
      uses: actions/download-artifact@v3
    
    - name: Generate firmware manifest
      run: |
        cat > firmware-manifest.json << EOF
        {
          "version": "${{ github.ref_name }}",
          "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
          "commit": "${{ github.sha }}",
          "firmware": [
        EOF
        
        # Add ESP32 firmware
        for file in firmware-esp32/*.bin; do
          if [ -f "$file" ]; then
            board=$(basename "$file" .bin)
            checksum=$(sha256sum "$file" | cut -d' ' -f1)
            size=$(stat -c%s "$file")
            cat >> firmware-manifest.json << EOF
            {
              "name": "$board",
              "board_type": "ESP32",
              "file": "$file",
              "checksum": "$checksum",
              "size": $size,
              "format": "bin"
            },
        EOF
          fi
        done
        
        # Add STM32 firmware
        for file in firmware-stm32f4/*.bin firmware-stm32f7/*.bin firmware-stm32h7/*.bin; do
          if [ -f "$file" ]; then
            board=$(basename "$file" .bin)
            checksum=$(sha256sum "$file" | cut -d' ' -f1)
            size=$(stat -c%s "$file")
            cat >> firmware-manifest.json << EOF
            {
              "name": "$board",
              "board_type": "STM32",
              "file": "$file",
              "checksum": "$checksum",
              "size": $size,
              "format": "bin"
            },
        EOF
          fi
        done
        
        # Add Arduino firmware
        for file in firmware-arduino_uno/*.hex firmware-arduino_nano/*.hex firmware-arduino_mega/*.hex; do
          if [ -f "$file" ]; then
            board=$(basename "$file" .hex)
            checksum=$(sha256sum "$file" | cut -d' ' -f1)
            size=$(stat -c%s "$file")
            cat >> firmware-manifest.json << EOF
            {
              "name": "$board",
              "board_type": "Arduino",
              "file": "$file",
              "checksum": "$checksum",
              "size": $size,
              "format": "hex"
            },
        EOF
          fi
        done
        
        # Remove trailing comma and close JSON
        sed -i '$ s/,$//' firmware-manifest.json
        echo "  ]" >> firmware-manifest.json
        echo "}" >> firmware-manifest.json
    
    - name: Create Release
      uses: softprops/action-gh-release@v1
      with:
        files: |
          firmware-esp32/*.bin
          firmware-stm32f4/*.bin
          firmware-stm32f7/*.bin
          firmware-stm32h7/*.bin
          firmware-arduino_uno/*.hex
          firmware-arduino_nano/*.hex
          firmware-arduino_mega/*.hex
          firmware-manifest.json
        body: |
          ## Firmware Release ${{ github.ref_name }}
          
          ### Changes
          - Automated build from commit ${{ github.sha }}
          - Built on $(date -u +%Y-%m-%dT%H:%M:%SZ)
          
          ### Supported Boards
          - ESP32 variants
          - STM32 variants
          - Arduino variants
          
          ### Installation
          Use the AWG-Kumulus Desktop Application to flash firmware:
          1. Connect your device
          2. Select firmware from GitHub release
          3. Flash automatically
        draft: false
        prerelease: false
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 4. Testing Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Test Firmware

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test-esp32:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install ESP-IDF
      uses: espressif/esp-idf-ci-action@v1
      with:
        esp_idf_version: 'v4.4'
    
    - name: Run unit tests
      run: |
        idf.py set-target esp32
        idf.py build
        idf.py test
    
    - name: Run integration tests
      run: |
        python -m pytest tests/integration/ -v

  test-stm32:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up ARM toolchain
      run: |
        sudo apt-get update
        sudo apt-get install -y gcc-arm-none-eabi
    
    - name: Run unit tests
      run: |
        make BOARD=stm32f4 test
    
    - name: Run integration tests
      run: |
        python -m pytest tests/stm32/ -v
```

## GitLab CI/CD Setup

### 1. Repository Structure

```
firmware-project/
├── .gitlab-ci.yml
├── .gitlab/
│   ├── ci/
│   │   ├── build-esp32.yml
│   │   ├── build-stm32.yml
│   │   └── build-arduino.yml
│   └── docker/
│       ├── esp32.Dockerfile
│       ├── stm32.Dockerfile
│       └── arduino.Dockerfile
├── src/
├── tests/
└── README.md
```

### 2. Main GitLab CI Configuration

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - build
  - release

variables:
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"

# Include job definitions
include:
  - local: '.gitlab/ci/build-esp32.yml'
  - local: '.gitlab/ci/build-stm32.yml'
  - local: '.gitlab/ci/build-arduino.yml'

# Test stage
test:esp32:
  stage: test
  image: espressif/idf:latest
  script:
    - idf.py set-target esp32
    - idf.py build
    - idf.py test
  only:
    - main
    - develop
    - merge_requests

test:stm32:
  stage: test
  image: stm32-toolchain:latest
  script:
    - make BOARD=stm32f4 test
  only:
    - main
    - develop
    - merge_requests

# Release stage
create_release:
  stage: release
  image: alpine:latest
  before_script:
    - apk add --no-cache curl jq
  script:
    - |
      # Create release notes
      cat > release_notes.md << EOF
      ## Firmware Release $CI_COMMIT_TAG
      
      ### Build Information
      - Commit: $CI_COMMIT_SHA
      - Pipeline: $CI_PIPELINE_ID
      - Built: $(date -u +%Y-%m-%dT%H:%M:%SZ)
      
      ### Firmware Files
      EOF
      
      # List all firmware files
      find . -name "*.bin" -o -name "*.hex" | while read file; do
        echo "- $(basename "$file")" >> release_notes.md
      done
      
      # Create release
      curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
           --header "Content-Type: application/json" \
           --data "{
             \"tag_name\": \"$CI_COMMIT_TAG\",
             \"description\": \"$(cat release_notes.md)\",
             \"assets\": {
               \"links\": []
             }
           }" \
           --request POST \
           "$CI_API_V4_URL/projects/$CI_PROJECT_ID/releases"
  only:
    - tags
  dependencies:
    - build:esp32
    - build:stm32
    - build:arduino
```

### 3. ESP32 Build Job

Create `.gitlab/ci/build-esp32.yml`:

```yaml
build:esp32:
  stage: build
  image: espressif/idf:latest
  variables:
    BOARD: "esp32"
  script:
    - idf.py set-target $BOARD
    - idf.py build
    - |
      # Create firmware package
      mkdir -p firmware-package/esp32
      cp build/*.bin firmware-package/esp32/
      
      # Generate checksums
      cd firmware-package/esp32
      for file in *.bin; do
        echo "$(sha256sum "$file" | cut -d' ' -f1)  $file" > "$file.sha256"
      done
      cd ../..
      
      # Create archive
      tar -czf firmware-esp32-$CI_COMMIT_TAG.tar.gz firmware-package/
  artifacts:
    paths:
      - firmware-esp32-$CI_COMMIT_TAG.tar.gz
      - firmware-package/
    expire_in: 30 days
  only:
    - main
    - develop
    - tags

build:esp32-s2:
  extends: build:esp32
  variables:
    BOARD: "esp32s2"

build:esp32-s3:
  extends: build:esp32
  variables:
    BOARD: "esp32s3"
```

### 4. STM32 Build Job

Create `.gitlab/ci/build-stm32.yml`:

```yaml
build:stm32:
  stage: build
  image: stm32-toolchain:latest
  variables:
    BOARD: "stm32f4"
  script:
    - make BOARD=$BOARD clean
    - make BOARD=$BOARD all
    - |
      # Create firmware package
      mkdir -p firmware-package/stm32
      cp build/*.bin firmware-package/stm32/
      
      # Generate checksums
      cd firmware-package/stm32
      for file in *.bin; do
        echo "$(sha256sum "$file" | cut -d' ' -f1)  $file" > "$file.sha256"
      done
      cd ../..
      
      # Create archive
      tar -czf firmware-stm32-$CI_COMMIT_TAG.tar.gz firmware-package/
  artifacts:
    paths:
      - firmware-stm32-$CI_COMMIT_TAG.tar.gz
      - firmware-package/
    expire_in: 30 days
  only:
    - main
    - develop
    - tags

build:stm32f7:
  extends: build:stm32
  variables:
    BOARD: "stm32f7"

build:stm32h7:
  extends: build:stm32
  variables:
    BOARD: "stm32h7"
```

### 5. Arduino Build Job

Create `.gitlab/ci/build-arduino.yml`:

```yaml
build:arduino:
  stage: build
  image: platformio/platformio:latest
  variables:
    BOARD: "arduino_uno"
  script:
    - pio run -e $BOARD
    - |
      # Create firmware package
      mkdir -p firmware-package/arduino
      cp .pio/build/$BOARD/firmware.hex firmware-package/arduino/$BOARD.hex
      
      # Generate checksums
      cd firmware-package/arduino
      for file in *.hex; do
        echo "$(sha256sum "$file" | cut -d' ' -f1)  $file" > "$file.sha256"
      done
      cd ../..
      
      # Create archive
      tar -czf firmware-arduino-$CI_COMMIT_TAG.tar.gz firmware-package/
  artifacts:
    paths:
      - firmware-arduino-$CI_COMMIT_TAG.tar.gz
      - firmware-package/
    expire_in: 30 days
  only:
    - main
    - develop
    - tags

build:arduino_nano:
  extends: build:arduino
  variables:
    BOARD: "arduino_nano"

build:arduino_mega:
  extends: build:arduino
  variables:
    BOARD: "arduino_mega"
```

### 6. Docker Images for GitLab

Create `.gitlab/docker/esp32.Dockerfile`:

```dockerfile
FROM espressif/idf:latest

# Install additional tools
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy build scripts
COPY scripts/ /scripts/
RUN chmod +x /scripts/*.sh

CMD ["/bin/bash"]
```

Create `.gitlab/docker/stm32.Dockerfile`:

```dockerfile
FROM ubuntu:20.04

# Install STM32 toolchain
RUN apt-get update && apt-get install -y \
    gcc-arm-none-eabi \
    make \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy build scripts
COPY scripts/ /scripts/
RUN chmod +x /scripts/*.sh

CMD ["/bin/bash"]
```

## Firmware Build Workflows

### 1. ESP32 Build Process

```bash
#!/bin/bash
# scripts/build-esp32.sh

set -e

BOARD=${1:-esp32}
VERSION=${2:-$(git describe --tags --always)}

echo "Building ESP32 firmware for board: $BOARD"
echo "Version: $VERSION"

# Set target
idf.py set-target $BOARD

# Configure build
idf.py menuconfig

# Build firmware
idf.py build

# Generate version info
echo "const char* FIRMWARE_VERSION = \"$VERSION\";" > src/version.h
echo "const char* BUILD_DATE = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\";" >> src/version.h

# Rebuild with version info
idf.py build

# Create release package
mkdir -p release/$BOARD
cp build/*.bin release/$BOARD/
cp build/bootloader/*.bin release/$BOARD/ 2>/dev/null || true
cp build/partition_table/*.bin release/$BOARD/ 2>/dev/null || true

# Generate checksums
cd release/$BOARD
for file in *.bin; do
    sha256sum "$file" > "$file.sha256"
done
cd ../..

echo "Build completed successfully!"
```

### 2. STM32 Build Process

```bash
#!/bin/bash
# scripts/build-stm32.sh

set -e

BOARD=${1:-stm32f4}
VERSION=${2:-$(git describe --tags --always)}

echo "Building STM32 firmware for board: $BOARD"
echo "Version: $VERSION"

# Clean previous build
make BOARD=$BOARD clean

# Set version
export FIRMWARE_VERSION=$VERSION
export BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Build firmware
make BOARD=$BOARD all

# Create release package
mkdir -p release/$BOARD
cp build/*.bin release/$BOARD/
cp build/*.elf release/$BOARD/ 2>/dev/null || true

# Generate checksums
cd release/$BOARD
for file in *.bin *.elf; do
    if [ -f "$file" ]; then
        sha256sum "$file" > "$file.sha256"
    fi
done
cd ../..

echo "Build completed successfully!"
```

### 3. Arduino Build Process

```bash
#!/bin/bash
# scripts/build-arduino.sh

set -e

BOARD=${1:-arduino_uno}
VERSION=${2:-$(git describe --tags --always)}

echo "Building Arduino firmware for board: $BOARD"
echo "Version: $VERSION"

# Set version in source
echo "const char* FIRMWARE_VERSION = \"$VERSION\";" > src/version.h
echo "const char* BUILD_DATE = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\";" >> src/version.h

# Build firmware
pio run -e $BOARD

# Create release package
mkdir -p release/$BOARD
cp .pio/build/$BOARD/firmware.hex release/$BOARD/

# Generate checksums
cd release/$BOARD
for file in *.hex; do
    sha256sum "$file" > "$file.sha256"
done
cd ../..

echo "Build completed successfully!"
```

## Release Management

### 1. Semantic Versioning

Use semantic versioning for firmware releases:

```bash
# Major version (breaking changes)
git tag v2.0.0
git push origin v2.0.0

# Minor version (new features)
git tag v1.1.0
git push origin v1.1.0

# Patch version (bug fixes)
git tag v1.0.1
git push origin v1.0.1

# Pre-release versions
git tag v1.1.0-beta.1
git push origin v1.1.0-beta.1
```

### 2. Changelog Generation

Create `scripts/generate-changelog.sh`:

```bash
#!/bin/bash

PREVIOUS_TAG=${1:-$(git describe --tags --abbrev=0 HEAD^)}
CURRENT_TAG=${2:-$(git describe --tags --abbrev=0 HEAD)}

echo "# Changelog"
echo ""
echo "## [$CURRENT_TAG] - $(date +%Y-%m-%d)"
echo ""

# Get commits between tags
git log --pretty=format:"- %s" $PREVIOUS_TAG..$CURRENT_TAG | grep -v "Merge pull request" | grep -v "Merge branch"

echo ""
echo "### Changes"
echo "- Updated from $PREVIOUS_TAG to $CURRENT_TAG"
echo "- Built from commit $(git rev-parse HEAD)"
echo "- Build date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

### 3. Release Automation

Create `scripts/create-release.sh`:

```bash
#!/bin/bash

set -e

TAG=${1:-$(git describe --tags --abbrev=0)}
REPO=${2:-$(git remote get-url origin | sed 's/.*github.com[:/]\([^.]*\).*/\1/')}

echo "Creating release for tag: $TAG"
echo "Repository: $REPO"

# Generate changelog
./scripts/generate-changelog.sh > CHANGELOG.md

# Create GitHub release
gh release create $TAG \
    --title "Firmware Release $TAG" \
    --notes-file CHANGELOG.md \
    --latest \
    build/*.bin \
    build/*.hex \
    firmware-manifest.json

echo "Release created successfully!"
```

## Integration with Desktop App

### 1. GitHub Integration

The desktop application can automatically detect and use GitHub releases:

```python
# Example: Add firmware from GitHub release
firmware_id = firmware_manager.add_firmware_from_github(
    repo="your-org/firmware-repo",
    release_tag="v1.0.0",
    asset_name="firmware.bin",
    board_type="ESP32"
)

# Flash the firmware
success = flasher.flash_firmware_by_id(device, firmware_id)
```

### 2. GitLab Integration

For GitLab, use project ID and pipeline information:

```python
# Example: Add firmware from GitLab pipeline
firmware_id = firmware_manager.add_firmware_from_gitlab(
    project_id="123456",
    pipeline_id="789012",
    artifact_name="build",
    board_type="STM32"
)

# Flash the firmware
success = flasher.flash_firmware_by_id(device, firmware_id)
```

### 3. Automatic Update Checking

```python
# Check for updates from GitHub
def check_github_updates(repo, current_version):
    try:
        response = requests.get(f"https://api.github.com/repos/{repo}/releases/latest")
        response.raise_for_status()
        latest_release = response.json()
        
        if latest_release['tag_name'] != current_version:
            return {
                'available': True,
                'version': latest_release['tag_name'],
                'url': latest_release['html_url'],
                'notes': latest_release['body']
            }
    except Exception as e:
        logger.error(f"Failed to check GitHub updates: {e}")
    
    return {'available': False}

# Check for updates from GitLab
def check_gitlab_updates(project_id, current_version):
    try:
        response = requests.get(f"https://gitlab.com/api/v4/projects/{project_id}/releases")
        response.raise_for_status()
        releases = response.json()
        
        if releases and releases[0]['tag_name'] != current_version:
            return {
                'available': True,
                'version': releases[0]['tag_name'],
                'url': releases[0]['_links']['self'],
                'notes': releases[0]['description']
            }
    except Exception as e:
        logger.error(f"Failed to check GitLab updates: {e}")
    
    return {'available': False}
```

## Best Practices

### 1. Security

- **Use secrets for tokens**: Store API tokens in GitHub Secrets or GitLab Variables
- **Sign releases**: Use GPG signing for release integrity
- **Validate checksums**: Always verify firmware checksums before flashing
- **Limit permissions**: Use minimal required permissions for CI/CD

### 2. Performance

- **Parallel builds**: Use matrix strategies for multiple board types
- **Caching**: Cache dependencies and build artifacts
- **Incremental builds**: Only rebuild changed components
- **Artifact retention**: Set appropriate retention periods

### 3. Quality Assurance

- **Automated testing**: Run unit and integration tests
- **Code quality**: Use linting and formatting tools
- **Security scanning**: Scan for vulnerabilities
- **Documentation**: Keep documentation up to date

### 4. Monitoring

- **Build notifications**: Set up notifications for build failures
- **Metrics**: Track build times and success rates
- **Logging**: Comprehensive logging for debugging
- **Alerts**: Alert on critical failures

## Troubleshooting

### Common Issues

#### 1. Build Failures
- Check toolchain versions
- Verify dependencies
- Review build logs
- Test locally first

#### 2. Artifact Issues
- Check file paths
- Verify permissions
- Ensure proper naming
- Test artifact downloads

#### 3. Release Problems
- Verify tag format
- Check release notes
- Confirm file uploads
- Test release URLs

#### 4. Integration Issues
- Verify API tokens
- Check repository access
- Test API endpoints
- Review error logs

### Debug Commands

```bash
# Test GitHub API access
curl -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/repos/owner/repo/releases

# Test GitLab API access
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     https://gitlab.com/api/v4/projects/PROJECT_ID/releases

# Verify firmware checksums
sha256sum firmware.bin
```

### Support Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [ESP-IDF Build System](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/build-system.html)
- [STM32 Development Tools](https://www.st.com/en/development-tools/stm32cubeprog.html)

---

This guide provides comprehensive setup instructions for both GitHub Actions and GitLab CI/CD pipelines, enabling automated firmware builds and releases that integrate seamlessly with the AWG-Kumulus Desktop Application.
