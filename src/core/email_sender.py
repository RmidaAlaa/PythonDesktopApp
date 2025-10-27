"""Email functionality with secure credential storage."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional

import keyring
from .logger import setup_logger

logger = setup_logger("EmailSender")


class EmailSender:
    """Sends emails with SMTP using keyring for credentials."""
    
    SERVICE_NAME = "AWG-Kumulus"
    
    def __init__(self):
        self.logger = logger
    
    def save_credentials(self, username: str, password: str):
        """Save SMTP credentials using keyring."""
        try:
            keyring.set_password(self.SERVICE_NAME, username, password)
            logger.info(f"Saved credentials for {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False
    
    def get_password(self, username: str) -> Optional[str]:
        """Retrieve password from keyring."""
        try:
            return keyring.get_password(self.SERVICE_NAME, username)
        except Exception as e:
            logger.error(f"Failed to retrieve password: {e}")
            return None
    
    def send_email(self, smtp_config: dict, recipients: List[str], 
                   subject: str, body: str, attachment_path: Optional[Path] = None,
                   progress_callback=None) -> bool:
        """Send an email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = smtp_config.get('username', '')
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach file if provided
            if attachment_path and attachment_path.exists():
                with open(attachment_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename={attachment_path.name}'
                    )
                    msg.attach(part)
            
            # Get password from keyring
            password = self.get_password(smtp_config.get('username', ''))
            if not password:
                logger.error("Password not found in keyring")
                return False
            
            # Connect to server
            if progress_callback:
                progress_callback("Connecting to SMTP server...")
            
            server = smtplib.SMTP(smtp_config['host'], smtp_config['port'])
            
            if smtp_config.get('tls', True):
                server.starttls()
            
            if progress_callback:
                progress_callback("Logging in...")
            
            server.login(smtp_config.get('username', ''), password)
            
            if progress_callback:
                progress_callback("Sending email...")
            
            text = msg.as_string()
            server.send_message(msg)
            server.quit()
            
            if progress_callback:
                progress_callback("Email sent successfully!")
            
            logger.info(f"Email sent to {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False

