#!/usr/bin/env python
"""
Direct Email Sender - Brave Method
This bypasses potential issues and sends emails directly via SMTP with retry logic
"""

import smtplib
import ssl
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple


class DirectEmailSender:
    """
    Brave Method: Direct SMTP email sender with retry logic
    Handles Gmail and other SMTP servers
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        display_name: str = "Horilla EMS",
        retries: int = 3,
    ):
        """
        Initialize email sender

        Args:
            smtp_host: SMTP server host (e.g., smtp.gmail.com)
            smtp_port: SMTP server port (usually 587 for TLS, 465 for SSL)
            username: Email username
            password: Email password or app password
            from_email: Sender email address
            display_name: Display name for emails
            retries: Number of retry attempts
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.display_name = display_name
        self.retries = retries

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        use_html: bool = False,
        async_send: bool = False,
    ) -> Tuple[bool, str]:
        """
        Send email with retry logic

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            use_html: Whether body is HTML
            async_send: Send asynchronously

        Returns:
            Tuple of (success: bool, message: str)
        """
        if async_send:
            thread = threading.Thread(
                target=self._send_with_retry, args=(to_email, subject, body, use_html)
            )
            thread.daemon = True
            thread.start()
            return True, "Email queued for sending"
        else:
            return self._send_with_retry(to_email, subject, body, use_html)

    def _send_with_retry(
        self, to_email: str, subject: str, body: str, use_html: bool = False
    ) -> Tuple[bool, str]:
        """
        Send email with automatic retry on failure
        """
        last_error = None

        for attempt in range(1, self.retries + 1):
            try:
                print(
                    f"[Attempt {attempt}/{self.retries}] Sending email to {to_email}..."
                )

                # Create message
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{self.display_name} <{self.from_email}>"
                msg["To"] = to_email

                # Add body
                mime_type = "html" if use_html else "plain"
                msg.attach(MIMEText(body, mime_type, "utf-8"))

                # Connect to SMTP server
                print(
                    f"[Attempt {attempt}] Connecting to {self.smtp_host}:{self.smtp_port}..."
                )

                context = ssl.create_default_context()

                # Use STARTTLS for port 587
                if self.smtp_port == 587:
                    with smtplib.SMTP(
                        self.smtp_host, self.smtp_port, timeout=15
                    ) as server:
                        server.starttls(context=context)
                        print(f"[Attempt {attempt}] TLS started, authenticating...")
                        server.login(self.username, self.password)
                        print(f"[Attempt {attempt}] Authentication successful!")
                        server.send_message(msg)
                        print(f"[Attempt {attempt}] Email sent successfully!")
                        return True, f"Email sent to {to_email}"

                # Use implicit SSL for port 465
                elif self.smtp_port == 465:
                    with smtplib.SMTP_SSL(
                        self.smtp_host, self.smtp_port, timeout=15, context=context
                    ) as server:
                        print(f"[Attempt {attempt}] Authenticating...")
                        server.login(self.username, self.password)
                        print(f"[Attempt {attempt}] Authentication successful!")
                        server.send_message(msg)
                        print(f"[Attempt {attempt}] Email sent successfully!")
                        return True, f"Email sent to {to_email}"

            except smtplib.SMTPAuthenticationError as e:
                last_error = f"Authentication failed: {str(e)}"
                print(f"[Attempt {attempt}] {last_error}")

                if "Username and Password not accepted" in str(e):
                    print("  ⚠️ SOLUTION: Check your Gmail App Password")
                    print("  1. Go to https://myaccount.google.com/apppasswords")
                    print("  2. Generate a new 16-character password")
                    print("  3. Update the password in email configuration")
                    return False, last_error

            except smtplib.SMTPException as e:
                last_error = f"SMTP error: {str(e)}"
                print(f"[Attempt {attempt}] {last_error}")

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                print(f"[Attempt {attempt}] {last_error}")

            # Wait before retry
            if attempt < self.retries:
                wait_time = 2 ** (attempt - 1)  # Exponential backoff: 1, 2, 4 seconds
                print(
                    f"[Attempt {attempt}] Waiting {wait_time} seconds before retry..."
                )
                time.sleep(wait_time)

        # All retries failed
        print(f"❌ Failed to send email after {self.retries} attempts")
        return False, last_error or "Failed to send email"

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test SMTP connection without sending email

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Handle console/file backends
        if self.smtp_host in ["console", "file", ""]:
            return (
                True,
                f"Using {self.smtp_host or 'console'} backend - no connection test needed",
            )

        try:
            print(f"Testing connection to {self.smtp_host}:{self.smtp_port}...")

            context = ssl.create_default_context()

            if self.smtp_port == 587:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                    print("✅ Connected successfully")
                    server.starttls(context=context)
                    print("✅ TLS started")
                    server.login(self.username, self.password)
                    print("✅ Authentication successful!")
                    return True, "Connection test passed"

            elif self.smtp_port == 465:
                with smtplib.SMTP_SSL(
                    self.smtp_host, self.smtp_port, timeout=10, context=context
                ) as server:
                    print("✅ Connected successfully (SSL)")
                    server.login(self.username, self.password)
                    print("✅ Authentication successful!")
                    return True, "Connection test passed"

        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Authentication failed: {str(e)}")
            return False, f"Authentication error: {str(e)}"

        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
            return False, f"Connection error: {str(e)}"


# Test the brave method
if __name__ == "__main__":
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
    django.setup()

    from base.models import DynamicEmailConfiguration

    print("=" * 70)
    print("BRAVE METHOD - DIRECT EMAIL SENDER TEST")
    print("=" * 70)
    print()

    # Get email config from database
    config = DynamicEmailConfiguration.objects.filter(is_primary=True).first()

    if not config:
        print("❌ No email configuration found!")
        print("Please configure email first via quick_email_setup.py")
    else:
        print("✅ Email Configuration Found:")
        print(f"   Host: {config.host}")
        print(f"   Port: {config.port}")
        print(f"   From: {config.from_email}")
        print()

        # Create sender
        sender = DirectEmailSender(
            smtp_host=config.host,
            smtp_port=config.port,
            username=config.username,
            password=config.password,
            from_email=config.from_email,
            display_name=config.display_name or "Horilla EMS",
            retries=3,
        )

        # Test connection
        print("🧪 Testing SMTP Connection...")
        print("-" * 70)
        success, msg = sender.test_connection()
        print()

        if success:
            print("✅ Connection test passed!")
            print()

            # Send test email
            test_email = input("Enter email to send test: ").strip()
            if test_email:
                print()
                print("📧 Sending test email...")
                print("-" * 70)
                success, msg = sender.send_email(
                    to_email=test_email,
                    subject="Test Email - Horilla EMS Brave Method",
                    body="""Hello,

This is a test email from Horilla EMS using the Brave Method email sender.

If you received this email, the email system is working correctly!

Best regards,
Horilla EMS Team""",
                )
                print()
                print(f"Result: {msg}")
        else:
            print(f"❌ Connection test failed: {msg}")
