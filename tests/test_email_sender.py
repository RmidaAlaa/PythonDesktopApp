"""Tests for email sending functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from src.core.email_sender import EmailSender

class TestEmailSender:
    """Test cases for EmailSender."""
    
    @pytest.fixture
    def email_sender(self):
        return EmailSender()
        
    @patch('keyring.set_password')
    def test_save_credentials(self, mock_keyring_set, email_sender):
        """Test saving credentials."""
        result = email_sender.save_credentials("user@example.com", "password123")
        
        assert result is True
        mock_keyring_set.assert_called_with(EmailSender.SERVICE_NAME, "user@example.com", "password123")
        
    @patch('keyring.get_password')
    def test_get_password(self, mock_keyring_get, email_sender):
        """Test retrieving password."""
        mock_keyring_get.return_value = "secret"
        
        password = email_sender.get_password("user@example.com")
        assert password == "secret"
        
    @patch('smtplib.SMTP')
    @patch('src.core.email_sender.EmailSender.get_password')
    def test_send_email_success(self, mock_get_pass, mock_smtp, email_sender):
        """Test sending email successfully."""
        mock_get_pass.return_value = "password"
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        config = {
            "host": "smtp.example.com",
            "port": 587,
            "username": "user@example.com",
            "tls": True
        }
        
        result = email_sender.send_email(
            config,
            ["recipient@example.com"],
            "Subject",
            "Body"
        )
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_with("user@example.com", "password")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch('src.core.email_sender.EmailSender.get_password')
    def test_send_email_no_password(self, mock_get_pass, email_sender):
        """Test sending email when password is missing."""
        mock_get_pass.return_value = None
        
        result = email_sender.send_email({}, [], "", "")
        assert result is False
