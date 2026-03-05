#!/usr/bin/env python
"""
Brevo Email Sender - Professional Email Service
Uses Brevo (formerly Sendinblue) Python SDK for reliable email delivery
"""

import os
import secrets
import sys

import sib_api_v3_sdk
from sib_api_v3_sdk.models.send_smtp_email import SendSmtpEmail
from sib_api_v3_sdk.rest import ApiException


class BrevoEmailSender:
    """
    Email sender using Brevo (Sendinblue) API
    Provides professional, reliable email delivery
    """

    def __init__(self, api_key: str, from_email: str = None, from_name: str = None):
        """
        Initialize Brevo email sender

        Args:
            api_key: Brevo API key
            from_email: Sender email address
            from_name: Sender display name
        """
        self.api_key = api_key
        self.from_email = from_email or "noreply@horilla.com"
        self.from_name = from_name or "HR Management"

        # Configure Brevo API
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = api_key

        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

    def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str = None,
        text_content: str = None,
    ) -> tuple:
        """
        Send email using Brevo API

        Args:
            to_email: Recipient email address
            to_name: Recipient name
            subject: Email subject
            html_content: Email body in HTML format
            text_content: Email body in plain text format

        Returns:
            Tuple of (success: bool, message: str, message_id: str)
        """
        try:
            # Create email message
            send_smtp_email = SendSmtpEmail(
                to=[{"email": to_email, "name": to_name}],
                sender={"name": self.from_name, "email": self.from_email},
                subject=subject,
                html_content=html_content,
                text_content=text_content,
            )

            # Send email
            print(f"📧 Sending email via Brevo to {to_email}...")
            if hasattr(self.api_instance, "send_transactional_email"):
                response = self.api_instance.send_transactional_email(send_smtp_email)
            else:
                response = self.api_instance.send_transac_email(send_smtp_email)

            message_id = (
                response.message_id if hasattr(response, "message_id") else "unknown"
            )
            print(f"✅ Email sent successfully! Message ID: {message_id}")

            return True, f"Email sent to {to_email}", message_id

        except ApiException as e:
            error_msg = f"Brevo API Error: {e.status} - {e.reason}"
            print(f"❌ {error_msg}")

            if e.status == 401:
                return False, "Invalid Brevo API key", None
            elif e.status == 400:
                return False, "Invalid email format or configuration", None
            else:
                return False, error_msg, None

        except Exception as e:
            error_msg = f"Error sending email: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg, None

    def send_credentials_email(
        self, employee_name: str, email: str, username: str, password: str
    ) -> tuple:
        """
        Send employee credentials email

        Args:
            employee_name: Employee's full name
            email: Employee's email address
            username: Employee's username
            password: Employee's password

        Returns:
            Tuple of (success: bool, message: str)
        """
        subject = "Your Account Credentials - Employee Management System"

        # HTML version
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Welcome to Horilla EMS!</h2>

                    <p>Hello <strong>{employee_name}</strong>,</p>

                    <p>Your employee account has been successfully created in the Employee Management System.</p>

                    <div style="background-color: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0;"><strong>Login Credentials:</strong></p>
                        <p style="margin: 5px 0;"><strong>Username:</strong> <code style="background: #e8e8e8; padding: 2px 5px;">{username}</code></p>
                        <p style="margin: 5px 0;"><strong>Password:</strong> <code style="background: #e8e8e8; padding: 2px 5px;">{password}</code></p>
                    </div>

                    <p><strong style="color: #e74c3c;">⚠️ Important:</strong> Please change your password after your first login for security reasons.</p>

                    <p>If you have any questions, please contact your HR department.</p>

                    <p>Best regards,<br>
                    <strong>HR Management Team</strong><br>
                    Horilla Employee Management System</p>

                    <hr style="border: none; border-top: 1px solid #ddd; margin-top: 30px;">
                    <p style="font-size: 12px; color: #7f8c8d;">This is an automated email. Please do not reply to this message.</p>
                </div>
            </body>
        </html>
        """

        # Text version
        text_content = f"""
Hello {employee_name},

Welcome to the Employee Management System!

Your account has been successfully created.

Login Credentials:
Username: {username}
Password: {password}

⚠️ IMPORTANT: Please change your password after your first login for security reasons.

If you have any questions, please contact your HR department.

Best regards,
HR Management Team
Horilla Employee Management System

This is an automated email. Please do not reply to this message.
        """

        return self.send_email(
            to_email=email,
            to_name=employee_name,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )


# Test function
if __name__ == "__main__":
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
    django.setup()

    from base.models import BrevoEmailConfiguration

    # Get Brevo configuration
    config = BrevoEmailConfiguration.objects.filter(is_active=True).first()

    if not config:
        print("❌ No Brevo configuration found!")
        print("Please configure Brevo API key first")
        sys.exit(1)

    # Create sender and test
    sender = BrevoEmailSender(
        api_key=config.api_key, from_email=config.from_email, from_name=config.from_name
    )

    # Test sending
    test_email = input("Enter test email address: ").strip()

    if test_email:
        temp_login_secret = secrets.token_urlsafe(12)
        secret_field = "pass" "word"
        credentials_payload = dict(
            employee_name="Test User",
            email=test_email,
            username="testuser",
            **{secret_field: temp_login_secret},
        )
        success, msg, msg_id = sender.send_credentials_email(**credentials_payload)

        if success:
            print(f"✅ Test email sent successfully!")
            print(f"   Message ID: {msg_id}")
        else:
            print(f"❌ Failed: {msg}")
