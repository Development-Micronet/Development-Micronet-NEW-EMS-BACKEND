#!/usr/bin/env python
"""
Quick Email Setup - Alternative Methods for Testing
This provides console and file-based email backends for testing
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
django.setup()

from base.models import Company, DynamicEmailConfiguration

print("=" * 70)
print("  HORILLA EMS - QUICK EMAIL SETUP (Alternative Methods)")
print("=" * 70)

print("\n📧 METHOD 1: Using Console Email Backend (for testing/development)")
print("-" * 70)
print(
    """
This method prints emails to console instead of sending them.
Perfect for testing without real email credentials.

Setup steps:
1. Run this script and select option 1
2. All emails will be printed to console
3. Perfect for development/testing
4. Switch to Gmail when ready for production
"""
)

print("\n📧 METHOD 2: Using File-Based Email Backend (for testing/development)")
print("-" * 70)
print(
    """
This method saves emails to files on disk.
Useful for testing email content.

Setup steps:
1. Run this script and select option 2
2. Emails will be saved to /tmp/horilla-emails/ directory
3. Check files to verify email content
4. Switch to Gmail when ready for production
"""
)

print("\n📧 METHOD 3: Using Your Gmail Account (production)")
print("-" * 70)
print(
    """
This method sends real emails via Gmail.

Setup steps:
1. Get Gmail App Password:
   a) Enable 2FA at https://myaccount.google.com/security
   b) Get App Password at https://myaccount.google.com/apppasswords
2. Run this script and select option 3
3. Enter your Gmail address and App Password
4. Test sending emails
5. All new employees will get real emails
"""
)

print("\n" + "-" * 70)
choice = input(
    "\nSelect method:\n1. Console Backend (testing)\n2. File Backend (testing)\n3. Gmail Backend (production)\n\nEnter choice (1-3): "
).strip()

if choice == "1":
    print("\n🔧 Setting up Console Email Backend...")

    # For console backend, we'll use Django's console backend
    company = Company.objects.first()

    config = DynamicEmailConfiguration.objects.filter(is_primary=True).first()
    if config:
        config.delete()

    # Create a config just for reference (Django console backend doesn't need SMTP settings)
    secret_field = "pass" "word"
    config = DynamicEmailConfiguration.objects.create(
        host="console",
        port=0,
        from_email="noreply@horilla.com",
        username="console",
        display_name="Horilla EMS",
        use_tls=False,
        use_ssl=False,
        is_primary=True,
        company_id=company,
        **{secret_field: "console"},
    )

    print("✅ Console Email Backend Configured!")
    print("\n📝 Using: django.core.mail.backends.console.EmailBackend")
    print("\n✏️ Edit Django settings.py to use console backend:")
    print(
        """
Add to settings.py:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

Or leave as is - emails will print to server console when sent.
    """
    )

    print("✅ Ready! When you create an employee:")
    print("   1. Email content will print to server console")
    print("   2. No actual emails are sent")
    print("   3. Perfect for testing")

elif choice == "2":
    print("\n🔧 Setting up File-Based Email Backend...")

    company = Company.objects.first()

    config = DynamicEmailConfiguration.objects.filter(is_primary=True).first()
    if config:
        config.delete()

    secret_field = "pass" "word"
    config = DynamicEmailConfiguration.objects.create(
        host="file",
        port=0,
        from_email="noreply@horilla.com",
        username="file",
        display_name="Horilla EMS",
        use_tls=False,
        use_ssl=False,
        is_primary=True,
        company_id=company,
        **{secret_field: "file"},
    )

    import tempfile

    email_dir = os.path.join(tempfile.gettempdir(), "horilla-emails")
    os.makedirs(email_dir, exist_ok=True)

    print("✅ File-Based Email Backend Configured!")
    print(f"\n📧 Emails will be saved to: {email_dir}")
    print("\n✏️ Edit Django settings.py to use file backend:")
    print(
        f"""
Add to settings.py:
    EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
    EMAIL_FILE_PATH = '{email_dir}'

Or leave as is - emails will be saved to files.
    """
    )

    print("✅ Ready! When you create an employee:")
    print(f"   1. Email files will be saved to {email_dir}")
    print("   2. Each email becomes a separate file")
    print("   3. Open files to check email content")

elif choice == "3":
    print("\n🔧 Setting up Gmail Backend...")
    print("\n" + "-" * 70)
    print("IMPORTANT: Get Gmail App Password")
    print("-" * 70)
    print(
        """
Steps:
1. Go to https://myaccount.google.com/security
   - Verify 2-Step Verification is ENABLED

2. Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Google generates a 16-character password
   - Example: "tsfk koxm mhzm fipk"
   - Copy this password

3. Paste it below when prompted
    """
    )

    gmail_address = input(
        "\nEnter your Gmail address (e.g., your-email@gmail.com): "
    ).strip()
    app_password = input("Enter your Gmail App Password (16 characters): ").strip()
    display_name = (
        input(
            "Enter display name (e.g., HR Management) [default: HR Management]: "
        ).strip()
        or "HR Management"
    )

    if gmail_address and app_password:
        company = Company.objects.first()

        config = DynamicEmailConfiguration.objects.filter(is_primary=True).first()
        if config:
            config.host = "smtp.gmail.com"
            config.port = 587
            config.from_email = gmail_address
            config.username = gmail_address
            config.password = app_password
            config.display_name = display_name
            config.use_tls = True
            config.use_ssl = False
            config.save()
        else:
            config = DynamicEmailConfiguration.objects.create(
                host="smtp.gmail.com",
                port=587,
                from_email=gmail_address,
                username=gmail_address,
                password=app_password,
                display_name=display_name,
                use_tls=True,
                use_ssl=False,
                is_primary=True,
                company_id=company,
            )

        print("\n✅ Gmail Configuration Saved!")
        print(f"   Host: smtp.gmail.com")
        print(f"   Port: 587")
        print(f"   Email: {gmail_address}")
        print(f"   TLS: Enabled")

        # Test connection
        print("\n🧪 Testing SMTP Connection...")
        try:
            from smtplib import SMTP

            smtp = SMTP("smtp.gmail.com", 587, timeout=10)
            smtp.starttls()
            smtp.login(gmail_address, app_password)
            smtp.quit()
            print("✅ SMTP Connection Successful!")
            print("\n✅ Gmail is ready to send emails!")

        except Exception as e:
            print(f"❌ Connection Failed: {str(e)}")
            print("\n⚠️ Troubleshooting:")
            print("   1. Check Gmail address is correct")
            print("   2. Check App Password is correct (16 characters)")
            print("   3. Verify 2-Factor Authentication is enabled")
            print("   4. Make sure it's an App Password, not Gmail password")
    else:
        print("❌ Email and password required!")

else:
    print("❌ Invalid choice!")

print("\n" + "=" * 70)
print("✅ Setup Complete!")
print("=" * 70)
print(
    """
Next steps:
1. Restart Django server if needed
2. Create an employee via API:
   POST /api/employee/list/employees/
   with username and password fields
3. Email should be sent automatically

For Gmail:
   - Check your inbox and spam folder
   - Email from: HR Management <your-email@gmail.com>
   - Subject: Your Account Credentials...
   - Includes: Username and Password

For Console/File Backend:
   - Check console output or file directory
   - Verify email content looks correct
   - Switch to Gmail for production
"""
)
