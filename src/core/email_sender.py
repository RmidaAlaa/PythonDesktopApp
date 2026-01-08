"""Email functionality with secure credential storage."""

import smtplib
import requests
import base64
from msal import ConfidentialClientApplication
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
    """Sends emails with SMTP or Azure Graph API."""
    
    SERVICE_NAME = "AWG-Kumulus"
    
    def __init__(self):
        self.logger = logger
    
    @staticmethod
    def _validate_azure_config(cfg: dict) -> Optional[str]:
        required = ['client_id', 'tenant_id', 'client_secret', 'sender_email']
        missing = [k for k in required if not cfg.get(k)]
        if missing:
            return f"Missing Azure config fields: {', '.join(missing)}"
        return None
    
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
    
    def send_email_azure(self, azure_config: dict, recipients: List[str], 
                        subject: str, body: str, attachment_path: Optional[Path] = None,
                        progress_callback=None, sender_override: Optional[str] = None) -> bool:
        """Send email via Microsoft Graph API."""
        try:
            err = self._validate_azure_config(azure_config or {})
            if err:
                raise ValueError(err)
            if not recipients:
                raise ValueError("No recipients provided")
            if progress_callback:
                progress_callback("Authenticating with Azure...")
                
            # Acquire Access Token using MSAL
            # azure_config may provide either 'authority' or 'token_url' (e.g. https://login.microsoftonline.com/<TENANT_ID>)
            authority = azure_config.get('authority') or azure_config.get('token_url') or f"https://login.microsoftonline.com/{azure_config.get('tenant_id','common')}"

            app = ConfidentialClientApplication(
                client_id=azure_config['client_id'],
                authority=authority,
                client_credential=azure_config['client_secret']
            )

            token_response = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

            access_token = token_response.get('access_token')
            if not access_token:
                error = token_response.get('error_description') or token_response.get('error')
                raise Exception(f"Failed to obtain access token: {error}")
                
            # Prepare Email
            if progress_callback:
                progress_callback("Preparing email...")
                
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Attachments (only include if present)
            attachments = []
            if attachment_path and attachment_path.exists():
                with open(attachment_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode('utf-8')
                    attachments.append({
                        '@odata.type': '#microsoft.graph.fileAttachment',
                        'name': attachment_path.name,
                        'contentBytes': content
                    })

            # Build email message payload
            email_msg = {
                'message': {
                    'subject': subject,
                    'body': {
                        'contentType': 'Text',
                        'content': body
                    },
                    'toRecipients': [
                        {'emailAddress': {'address': r}} for r in recipients
                    ]
                },
                'saveToSentItems': False
            }

            if attachments:
                email_msg['message']['attachments'] = attachments
            
            # Send Email
            if progress_callback:
                progress_callback("Sending via Graph API...")
                
            # Use configured sender_email as the endpoint user for sendMail.
            # Allow sender_override only if it exactly matches configured sender to avoid permission errors
            configured_sender = azure_config.get('sender_email')
            if not configured_sender:
                raise ValueError("No sender email provided in Azure config")

            if sender_override and sender_override != configured_sender:
                logger.warning(f"Ignoring sender_override '{sender_override}' because it does not match configured Azure sender '{configured_sender}'. Using configured sender to avoid Graph permission issues.")

            user_id = configured_sender
            send_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/sendMail"

            # Debug/log payload keys (do NOT log tokens)
            logger.debug(f"Graph send URL: {send_url}")
            logger.debug(f"Email payload keys: {list(email_msg.keys())}")
            
            # If sender_override is provided, we can add it as Reply-To or From (if allowed)
            # But for simplicity and to avoid 403/404 errors if the operator email is not a user in the tenant,
            # we should stick to the configured sender_email for the endpoint.
            # We can mention the operator in the body (which is already done).
            response = requests.post(send_url, headers=headers, json=email_msg, timeout=20)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                # Log detailed error response from Graph API
                logger.error(f"Graph API Error Response: {response.text}")
                raise e
            
            logger.info(f"Email sent via Azure to {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email via Azure: {e}")
            if progress_callback:
                progress_callback(f"Azure Error: {str(e)}")
            return False

    def send_email(self, smtp_config: dict, recipients: List[str], 
                   subject: str, body: str, attachment_path: Optional[Path] = None,
                   progress_callback=None, password: Optional[str] = None,
                   azure_config: Optional[dict] = None, sender_override: Optional[str] = None) -> bool:
        """Send an email via SMTP or Azure.
        
        Args:
            smtp_config: Dictionary with 'host', 'port', 'username', 'tls' keys.
            recipients: List of email addresses.
            subject: Email subject.
            body: Email body.
            attachment_path: Optional path to file attachment.
            progress_callback: Optional callback for status updates.
            password: Optional explicit password (overrides keyring).
            azure_config: Optional Azure configuration. If provided and enabled, uses Azure.
            sender_override: Optional email address to use as sender (for Azure).
        """
        # Check if Azure is enabled
        if azure_config and azure_config.get('enabled'):
            return self.send_email_azure(azure_config, recipients, subject, body, attachment_path, progress_callback, sender_override)

        try:
            # Create message
            msg = MIMEMultipart()
            # Use sender_override if provided, otherwise fallback to config username
            sender_email = sender_override if sender_override else smtp_config.get('username', '')
            msg['From'] = sender_email
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
            
            # Get password (explicit or from keyring)
            if not password:
                password = self.get_password(smtp_config.get('username', ''))
             
            if not password:
                logger.error("Password not found (neither provided nor in keyring)")
                return False
            
            # Connect to server
            if progress_callback:
                progress_callback("Connecting to SMTP server...")
            server = smtplib.SMTP(smtp_config['host'], smtp_config['port'], timeout=20)
            
            if smtp_config.get('tls', True):
                try:
                    server.starttls()
                except Exception as e:
                    logger.warning(f"STARTTLS failed or not supported: {e}")
            
            if progress_callback:
                progress_callback("Logging in...")
            
            server.login(smtp_config.get('username', ''), password)
            
            if progress_callback:
                progress_callback("Sending email...")
            
            server.send_message(msg)
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass
            
            if progress_callback:
                progress_callback("Email sent successfully!")
            
            logger.info(f"Email sent to {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False

