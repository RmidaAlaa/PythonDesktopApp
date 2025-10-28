# Automatic Email Feature

## Overview

The AWG Kumulus Device Manager now automatically sends emails after report generation with user confirmation.

## How It Works

### Workflow

1. **User generates a report** by clicking "📊 Generate Excel Report"
2. **Report is created** and saved locally
3. **Confirmation dialog appears** showing:
   - Report file location
   - Data summary (Operator, Machine Type, Machine ID, Device count)
   - Question: "Is the data correct?"
4. **User options**:
   - **Click "Yes"** → Email is sent automatically with the report attached
   - **Click "No"** → Report is saved locally only

### Email Configuration

Before using auto-email, you need to configure SMTP settings:

1. Click **"⚙️ Configure Email"** button
2. Enter SMTP settings:
   - SMTP Server (e.g., `smtp.gmail.com`)
   - Port (e.g., `587`)
   - Username (your email address)
   - Password (stored securely using Windows Credential Manager)
   - Recipients (one per line)
3. Click **"OK"** to save

### Email Settings Dialog

The configuration dialog includes:
- **SMTP Server** field
- **Port** field (default: 587)
- **Email Username** field
- **Password** field (masked input, stored in keyring)
- **Recipients** text area (multi-line)
- **OK/Cancel** buttons

### Security

- Passwords are stored securely using the OS keyring:
  - **Windows**: Windows Credential Manager
  - **macOS**: Keychain
  - **Linux**: Secret Service
- No passwords are stored in plain text

### Email Content

The automatically sent email includes:
- **Subject**: `AWG Kumulus Report - {Machine Type} - {Machine ID}`
- **Body**: 
  ```
  AWG Kumulus Device Manager Report
  
  Operator: {Name} ({Email})
  Machine Type: {Type}
  Machine ID: {ID}
  Devices Detected: {Count}
  
  Please find the attached Excel report with device details.
  ```
- **Attachment**: The generated Excel report

### Progress Feedback

During email sending, you'll see:
- Progress bar updates
- Log messages in the log area:
  - "Connecting to SMTP server..."
  - "Sending email..."
  - "Email sent successfully!"
- Success/failure popup

## Usage Examples

### Example 1: Generate and Send Automatically

1. Fill in operator info
2. Select machine type and enter ID
3. Click "Generate Excel Report"
4. Review the data summary in the confirmation dialog
5. Click "Yes" to send email automatically
6. Email is sent with progress shown
7. Success popup confirms delivery

### Example 2: Save Locally Only

1. Generate report
2. Review data summary
3. Click "No" to save locally only
4. Report is saved in app data directory

### Example 3: Send Later

1. Generate report
2. Click "No" to save locally
3. Later, click "📧 Send Email" button
4. Email is sent with the last generated report

## Configuration Examples

### Gmail Configuration

```
SMTP Server: smtp.gmail.com
Port: 587
Username: your.email@gmail.com
Password: [your app-specific password]
Recipients: recipient@example.com
```

Note: Gmail requires an "App Password" for SMTP. Generate one at:
https://myaccount.google.com/apppasswords

### Outlook Configuration

```
SMTP Server: smtp-mail.outlook.com
Port: 587
Username: your.email@outlook.com
Password: [your password]
Recipients: recipient@example.com
```

### Office 365 Configuration

```
SMTP Server: smtp.office365.com
Port: 587
Username: your.email@company.com
Password: [your password]
Recipients: recipient@example.com
```

## Troubleshooting

### Email Not Configured

If you haven't configured email yet, a warning dialog will appear with options to:
- Configure email now
- Cancel and configure later

### Password Issues

- Ensure you're using an "App Password" for Gmail
- Check that SMTP credentials are correct
- Verify the password is saved in the keyring

### Connection Errors

- Check internet connection
- Verify SMTP server address and port
- Ensure firewall allows SMTP connections
- Some networks block port 587 - try port 465 with SSL

### No Recipients

- Add at least one recipient email address
- Verify recipient addresses are valid
- Use the "Configure Email" button to add recipients

## Code Changes

### Files Modified

- `src/gui/main_window.py`:
  - Added `last_report_path` to store generated reports
  - Modified `generate_report()` to show confirmation dialog
  - Added `send_email_automatically()` method
  - Updated `send_email()` to check configuration
  - Added `configure_email_dialog()` for email setup
  - Added email configuration button in UI

### New Features

1. **Confirmation dialog** after report generation
2. **Automatic email sending** with user confirmation
3. **Email configuration dialog** with secure password storage
4. **Progress feedback** during email sending
5. **Error handling** for email failures

## Benefits

- ✅ **Workflow efficiency**: One-click report generation and sending
- ✅ **Data verification**: Review data before sending
- ✅ **Security**: Passwords stored securely in OS keyring
- ✅ **User control**: Choose to send or save locally
- ✅ **Progress feedback**: See email sending status
- ✅ **Error handling**: Clear error messages if sending fails

