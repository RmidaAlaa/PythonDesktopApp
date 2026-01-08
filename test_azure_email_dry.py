#!/usr/bin/env python3
"""
Dry test: acquire MSAL token and build email payload without sending.
"""
import sys
import json
import base64
from pathlib import Path
from msal import ConfidentialClientApplication

# Load config
sys.path.insert(0, str(Path(__file__).parent))
from src.core.config import Config

config = Config.load_config()
azure_config = config.get('azure', {})

print("=" * 70)
print("DRY TEST: MSAL Token Acquisition & Email Payload Build")
print("=" * 70)

# 1. Print Azure config (without secrets)
print("\n[Azure Config]")
print(f"  enabled: {azure_config.get('enabled')}")
print(f"  client_id: {azure_config.get('client_id')}")
print(f"  tenant_id: {azure_config.get('tenant_id')}")
print(f"  sender_email: {azure_config.get('sender_email')}")
print(f"  authority: {azure_config.get('authority', 'NOT SET')}")
print(f"  token_url: {azure_config.get('token_url', 'NOT SET')}")

# 2. Acquire token
print("\n[MSAL Token Acquisition]")
try:
    authority = (
        azure_config.get('authority')
        or azure_config.get('token_url')
        or f"https://login.microsoftonline.com/{azure_config.get('tenant_id', 'common')}"
    )
    print(f"  Authority URL: {authority}")
    
    app = ConfidentialClientApplication(
        client_id=azure_config['client_id'],
        authority=authority,
        client_credential=azure_config['client_secret']
    )
    
    print("  Attempting acquire_token_for_client()...")
    token_response = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    
    access_token = token_response.get('access_token')
    if access_token:
        print(f"  [OK] Token acquired successfully!")
        print(f"  Token length: {len(access_token)} chars")
        print(f"  Token preview: {access_token[:50]}...")
    else:
        error = token_response.get('error_description') or token_response.get('error')
        print(f"  [ERROR] Failed to acquire token: {error}")
        sys.exit(1)

except Exception as e:
    print(f"  [ERROR] Exception during token acquisition: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Build email payload
print("\n[Email Payload Construction]")
recipients = ['aabengandia@kumuluswater.com', 'test@example.com']
subject = "AWG Kumulus Report - Test Device - TEST-001"
body = "This is a test email body.\n\nNo attachment in this dry test."
attachment_path = None

# Build attachments list
attachments = []
if attachment_path and Path(attachment_path).exists():
    with open(attachment_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode('utf-8')
        attachments.append({
            '@odata.type': '#microsoft.graph.fileAttachment',
            'name': Path(attachment_path).name,
            'contentBytes': content
        })
    print(f"  Attachment added: {Path(attachment_path).name}")
else:
    print(f"  No attachment")

# Build payload
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

print(f"  Subject: {subject}")
print(f"  Recipients: {recipients}")
print(f"  Body length: {len(body)} chars")
print(f"  Attachments: {len(attachments)}")

# 4. Print full payload as JSON
print("\n[Full Email Payload (JSON)]")
print(json.dumps(email_msg, indent=2))

# 5. Print send URL
print("\n[Graph API Send URL]")
user_id = azure_config.get('sender_email')
send_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/sendMail"
print(f"  {send_url}")

# 6. Print request headers
print("\n[Request Headers (Bearer token not shown)]")
headers = {
    'Authorization': f'Bearer <token>',
    'Content-Type': 'application/json'
}
print(json.dumps(headers, indent=2))

print("\n" + "=" * 70)
print("[SUCCESS] Dry test completed. No network request was sent.")
print("=" * 70)
