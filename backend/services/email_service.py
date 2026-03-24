"""
Email service using Resend for transactional emails.
"""

from __future__ import annotations

import logging
import os

import resend

logger = logging.getLogger(__name__)


class EmailService:
    """Thin wrapper around the Resend SDK for sending transactional emails."""

    def __init__(self) -> None:
        api_key = os.getenv("RESEND_API_KEY")
        if not api_key:
            raise ValueError("RESEND_API_KEY environment variable is required")
        resend.api_key = api_key
        self.from_address = os.getenv("RESEND_FROM_ADDRESS", "noreply@contact.missingtable.com")
        self.app_base_url = os.getenv("APP_BASE_URL", "https://missingtable.com")

    def send_password_reset(self, to_email: str, reset_token: str, username: str) -> bool:
        """
        Send a password reset email via Resend.

        Args:
            to_email: Recipient email address
            reset_token: Signed JWT reset token
            username: User's username (for personalisation)

        Returns:
            True on success, False on failure
        """
        reset_url = f"{self.app_base_url}/?reset_token={reset_token}"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Reset your Missing Table password</title>
</head>
<body style="font-family: Arial, sans-serif; background: #f3f4f6; padding: 32px;">
  <div style="max-width: 480px; margin: 0 auto; background: #fff; border-radius: 8px; padding: 32px;">
    <h2 style="color: #2563eb;">Reset your password</h2>
    <p>Hi <strong>{username}</strong>,</p>
    <p>We received a request to reset the password for your Missing Table account.</p>
    <p>Click the button below to choose a new password. This link expires in <strong>1 hour</strong>.</p>
    <a href="{reset_url}"
       style="display: inline-block; margin: 16px 0; padding: 12px 24px;
              background: #2563eb; color: #fff; border-radius: 6px;
              text-decoration: none; font-weight: bold;">
      Reset Password
    </a>
    <p style="color: #6b7280; font-size: 13px;">
      If you didn't request this, you can safely ignore this email — your password won't change.
    </p>
    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;" />
    <p style="color: #9ca3af; font-size: 12px;">Missing Table · missingtable.com</p>
  </div>
</body>
</html>
"""

        text_body = (
            f"Hi {username},\n\n"
            "We received a request to reset the password for your Missing Table account.\n\n"
            f"Reset your password here (link expires in 1 hour):\n{reset_url}\n\n"
            "If you didn't request this, you can safely ignore this email.\n\n"
            "— Missing Table"
        )

        try:
            resend.Emails.send(
                {
                    "from": self.from_address,
                    "to": [to_email],
                    "subject": "Reset your Missing Table password",
                    "html": html_body,
                    "text": text_body,
                }
            )
            logger.info("password_reset_email_sent", extra={"recipient": to_email[:3] + "***"})
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            return False
