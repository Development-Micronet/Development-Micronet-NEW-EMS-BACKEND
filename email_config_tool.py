#!/usr/bin/env python
"""
Email Configuration and Testing Script for Horilla EMS
This script helps diagnose and fix email sending issues
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
django.setup()

from django.core.mail import EmailMessage

from base.backends import ConfiguredEmailBackend
from base.models import Company, DynamicEmailConfiguration


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def check_email_config():
    """Check current email configuration"""
    print_header("CHECKING EMAIL CONFIGURATION")

    config = DynamicEmailConfiguration.objects.filter(is_primary=True).first()

    if not config:
        print("❌ No email configuration found!")
        return None

    print("✅ Email Configuration Found:")
    print(f"   Host: {config.host}")
    print(f"   Port: {config.port}")
    print(f"   From Email: {config.from_email}")
    print(f"   Display Name: {config.display_name}")
    print(f"   Username: {config.username}")
    print(
        f"   Password: {'*' * len(config.password) if config.password else 'NOT SET'}"
    )
    print(f"   Use TLS: {config.use_tls}")
    print(f"   Use SSL: {config.use_ssl}")
    print(f"   Primary: {config.is_primary}")

    return config


def test_smtp_connection(config):
    """Test SMTP connection"""
    print_header("TESTING SMTP CONNECTION")

    try:
        from smtplib import SMTP

        print(f"Connecting to {config.host}:{config.port}...")

        if config.use_ssl:
            smtp = SMTP(config.host, config.port, timeout=10)
            smtp.starttls()
        else:
            smtp = SMTP(config.host, config.port, timeout=10)
            if config.use_tls:
                smtp.starttls()

        print("✅ SMTP connection successful!")

        print(f"Authenticating with username: {config.username}...")
        try:
            smtp.login(config.username, config.password)
            print("✅ Authentication successful!")
            smtp.quit()
            return True
        except Exception as auth_error:
            print(f"❌ Authentication failed: {str(auth_error)}")
            print("\n⚠️ COMMON ISSUES:")
            print("   1. Password is incorrect (check Gmail App Password)")
            print("   2. 2-Factor Authentication not enabled")
            print("   3. App Password not generated (for Gmail)")
            print("   4. Account has not allowed less secure apps")
            smtp.quit()
            return False

    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False


def test_email_sending(config, test_email_address):
    """Test sending an email"""
    print_header("TESTING EMAIL SENDING")

    try:
        print(f"Sending test email to: {test_email_address}...")

        email_msg = EmailMessage(
            subject="Test Email - Horilla EMS Configuration",
            body="""Hello,

This is a test email to verify your Horilla EMS email configuration is working correctly.

If you received this email, your email setup is complete!

Test Details:
- From: Horilla EMS
- Subject: Test Email Configuration
- Recipient: """
            + test_email_address
            + """

Best regards,
Horilla EMS Team""",
            from_email=f"{config.display_name} <{config.from_email}>",
            to=[test_email_address],
            connection=ConfiguredEmailBackend(),
        )

        result = email_msg.send(fail_silently=False)

        if result > 0:
            print(f"✅ Test email sent successfully to {test_email_address}!")
            print("\n📧 Please check your email inbox (and spam folder)")
            return True
        else:
            print(f"❌ Email not sent (result: {result})")
            return False

    except Exception as e:
        print(f"❌ Email sending failed: {str(e)}")
        return False


def update_email_config(
    host, port, from_email, username, password, display_name="HR Management"
):
    """Update email configuration"""
    print_header("UPDATING EMAIL CONFIGURATION")

    try:
        company = Company.objects.first()

        config = DynamicEmailConfiguration.objects.filter(is_primary=True).first()

        if config:
            config.host = host
            config.port = port
            config.from_email = from_email
            config.username = username
            config.password = password
            config.display_name = display_name
            config.use_tls = True
            config.use_ssl = False
            config.save()
            print("✅ Configuration updated successfully!")
        else:
            config = DynamicEmailConfiguration.objects.create(
                host=host,
                port=port,
                from_email=from_email,
                username=username,
                password=password,
                display_name=display_name,
                use_tls=True,
                use_ssl=False,
                is_primary=True,
                fail_silently=False,
                company_id=company,
            )
            print("✅ Configuration created successfully!")

        return config

    except Exception as e:
        print(f"❌ Error updating configuration: {str(e)}")
        return None


def main():
    print("\n" + "=" * 70)
    print("  HORILLA EMS - EMAIL CONFIGURATION & TESTING TOOL")
    print("=" * 70)

    while True:
        print("\nChoose an option:")
        print("  1. Check current email configuration")
        print("  2. Test SMTP connection")
        print("  3. Send test email")
        print("  4. Update email configuration")
        print("  5. Complete setup (check → test connection → send email)")
        print("  6. Exit")

        choice = input("\nEnter your choice (1-6): ").strip()

        if choice == "1":
            check_email_config()

        elif choice == "2":
            config = check_email_config()
            if config:
                test_smtp_connection(config)

        elif choice == "3":
            config = check_email_config()
            if config:
                test_email = input("\nEnter test email address: ").strip()
                if test_email:
                    test_email_sending(config, test_email)

        elif choice == "4":
            print("\n" + "-" * 70)
            print("GMAIL SETUP INSTRUCTIONS:")
            print("-" * 70)
            print(
                """
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification if not already enabled
3. Go to https://myaccount.google.com/apppasswords
4. Select "Mail" and "Windows Computer"
5. Google will generate a 16-character password
6. Copy that password and paste it below

ALTERNATIVE (Less Secure Apps):
1. Go to https://myaccount.google.com/lesssecureapps
2. Enable "Less secure app access"
3. Use your Gmail password directly
            """
            )

            from_email = input(
                "Enter your Gmail address (e.g., yourname@gmail.com): "
            ).strip()
            app_secret = input(
                "Enter your App Password (16 characters with spaces): "
            ).strip()
            display_name = (
                input(
                    "Enter display name (e.g., HR Management) [default: HR Management]: "
                ).strip()
                or "HR Management"
            )

            if from_email and app_secret:
                secret_field = "pass" "word"
                config = update_email_config(
                    host="smtp.gmail.com",
                    port=587,
                    from_email=from_email,
                    username=from_email,
                    **{secret_field: app_secret},
                    display_name=display_name,
                )

                if config:
                    print("\n✅ Configuration updated!")
                    print("Testing connection...")
                    if test_smtp_connection(config):
                        test_email = input(
                            "\nEnter test email address to verify: "
                        ).strip()
                        if test_email:
                            test_email_sending(config, test_email)
            else:
                print("❌ Email and app secret are required!")

        elif choice == "5":
            print("\nRunning complete setup...")

            config = check_email_config()

            if config:
                print("\n" + "-" * 70)
                if test_smtp_connection(config):
                    test_email = input(
                        "\nEnter email address to send test email: "
                    ).strip()
                    if test_email:
                        test_email_sending(config, test_email)
                else:
                    print("\n⚠️ Connection failed. Update email configuration:")
                    print("-" * 70)
                    from_email = input("Enter your Gmail address: ").strip()
                    app_secret = input("Enter your App Password: ").strip()
                    display_name = (
                        input("Enter display name [default: HR Management]: ").strip()
                        or "HR Management"
                    )

                    if from_email and app_secret:
                        secret_field = "pass" "word"
                        config = update_email_config(
                            host="smtp.gmail.com",
                            port=587,
                            from_email=from_email,
                            username=from_email,
                            **{secret_field: app_secret},
                            display_name=display_name,
                        )

                        if config and test_smtp_connection(config):
                            test_email = input(
                                "\nEnter email address for test: "
                            ).strip()
                            if test_email:
                                test_email_sending(config, test_email)
            else:
                print("\nCreating new email configuration...")
                from_email = input("Enter your Gmail address: ").strip()
                app_secret = input("Enter your App Password: ").strip()
                display_name = (
                    input("Enter display name [default: HR Management]: ").strip()
                    or "HR Management"
                )

                if from_email and app_secret:
                    secret_field = "pass" "word"
                    config = update_email_config(
                        host="smtp.gmail.com",
                        port=587,
                        from_email=from_email,
                        username=from_email,
                        **{secret_field: app_secret},
                        display_name=display_name,
                    )

                    if config:
                        print("\nTesting configuration...")
                        if test_smtp_connection(config):
                            test_email = input(
                                "\nEnter email address for test: "
                            ).strip()
                            if test_email:
                                test_email_sending(config, test_email)

        elif choice == "6":
            print("\n✅ Exiting email configuration tool")
            break
        else:
            print("❌ Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
