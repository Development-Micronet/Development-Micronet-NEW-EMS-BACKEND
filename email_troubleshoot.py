#!/usr/bin/env python
"""
Email Troubleshooting & Diagnostic Tool
Identifies why emails are not being sent
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
django.setup()

from base.models import DynamicEmailConfiguration

print("=" * 80)
print("EMAIL TROUBLESHOOTING & DIAGNOSTIC TOOL")
print("=" * 80)
print()

# Get configuration
config = DynamicEmailConfiguration.objects.filter(is_primary=True).first()

if not config:
    print("❌ ERROR: No email configuration found!")
    print()
    print("Solution:")
    print("  Run: python setup_gmail_brave.py")
    exit(1)

print("✅ Email Configuration Found:")
print("-" * 80)
print(f"Host: {config.host}")
print(f"Port: {config.port}")
print(f"From Email: {config.from_email}")
print(f"Username: {config.username}")
print(f"Password: {'*' * len(config.password)} (length: {len(config.password)})")
print(f"TLS: {config.use_tls}")
print(f"SSL: {config.use_ssl}")
print(f"Timeout: {config.timeout}")
print()

# Step 1: Test SMTP Connection
print("STEP 1: Testing SMTP Connection")
print("-" * 80)

try:
    print(f"Connecting to {config.host}:{config.port}...")
    context = ssl.create_default_context()

    if config.port == 587:
        server = smtplib.SMTP(config.host, config.port, timeout=15)
        print("✅ TCP Connection established")

        print("Upgrading to TLS...")
        server.starttls(context=context)
        print("✅ TLS started successfully")

    elif config.port == 465:
        server = smtplib.SMTP_SSL(config.host, config.port, timeout=15, context=context)
        print("✅ SSL Connection established")
    else:
        print(f"⚠️ Warning: Unusual port {config.port}")
        server = smtplib.SMTP(config.host, config.port, timeout=15)
        print("✅ TCP Connection established")

    print()
    print("STEP 2: Testing Authentication")
    print("-" * 80)
    print(f"Authenticating as: {config.username}")

    try:
        server.login(config.username, config.password)
        print("✅ Authentication SUCCESSFUL!")
        print()

        # Step 3: Send test email
        print("STEP 3: Sending Test Email")
        print("-" * 80)

        test_recipient = input("Enter email address to receive test email: ").strip()

        if not test_recipient:
            print("⚠️ No email provided, skipping test send")
        else:
            print(f"Sending test email to: {test_recipient}")

            # Create test message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"Test Email - Horilla EMS - {os.getenv('COMPUTERNAME', 'Unknown')}"
            )
            msg["From"] = f"HR Management <{config.from_email}>"
            msg["To"] = test_recipient

            body = """Hello,

This is a test email from Horilla EMS troubleshooting tool.

If you're receiving this email:
✅ SMTP Connection: WORKING
✅ Authentication: WORKING
✅ Email Sending: WORKING

The email system is fully operational!

If you received this in your inbox (not spam):
- Your configuration is correct
- Employee credentials emails should arrive normally
- Check spam folder for employee emails

Best regards,
Horilla EMS Team"""

            msg.attach(MIMEText(body, "plain", "utf-8"))

            try:
                server.send_message(msg)
                print("✅ Test email sent successfully!")
                print()
                print("=" * 80)
                print("WHAT TO DO NEXT:")
                print("=" * 80)
                print("1. Check your inbox for the test email")
                print("2. Check your SPAM folder")
                print("3. Wait 5-10 minutes if not received immediately")
                print()
                print("If you receive the test email:")
                print("  ✅ Email system is working")
                print("  ✅ Create employees normally via API")
                print("  ✅ They will receive credential emails")
                print()
                print("If you DON'T receive the test email:")
                print("  ❌ Check email configuration")
                print("  ❌ Verify Gmail app password")
                print("  ❌ Check Gmail security settings")
                print()

            except Exception as e:
                print(f"❌ Failed to send test email: {e}")
                print()

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication FAILED!")
        print(f"Error: {e}")
        print()
        print("SOLUTIONS:")
        print("-" * 80)
        print("1. Gmail App Password Issue:")
        print("   - Go to: https://myaccount.google.com/apppasswords")
        print("   - Generate a NEW 16-character password")
        print("   - Copy without spaces")
        print("   - Update configuration with new password")
        print()
        print("2. 2-Factor Authentication:")
        print("   - Make sure 2-Step Verification is ENABLED")
        print("   - Go to: https://myaccount.google.com/security")
        print("   - Enable if not already enabled")
        print()
        print("3. Update Password:")
        print("   - Run: python setup_gmail_brave.py")
        print("   - Select option to update email configuration")
        print()

    server.quit()
    print("✅ SMTP Connection closed")

except smtplib.SMTPException as e:
    print(f"❌ SMTP Error: {e}")
    print()
    print("SOLUTIONS:")
    print("-" * 80)
    print("1. Check internet connection")
    print("2. Verify Gmail SMTP settings:")
    print("   - Host: smtp.gmail.com ✓")
    print("   - Port: 587 ✓")
    print("   - TLS: Enabled ✓")
    print("3. Check firewall/network settings")
    print()

except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    print()
    print("SOLUTIONS:")
    print("-" * 80)
    print("1. Check Gmail account status")
    print("2. Verify all credentials are correct")
    print("3. Try resetting email configuration:")
    print("   - Run: python setup_gmail_brave.py")
    print()

print()
print("=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
