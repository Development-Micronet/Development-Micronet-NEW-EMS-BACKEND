#!/usr/bin/env python
"""
Email Verification Tool
Check if emails are being saved to disk
"""

import os
from pathlib import Path

print("=" * 80)
print("EMAIL VERIFICATION TOOL")
print("=" * 80)
print()

# Check email directory
email_dir = Path("emails")

print(f"📁 Email Directory: {email_dir.absolute()}")
print()

if not email_dir.exists():
    print("❌ Email directory does not exist!")
    print("   Creating directory...")
    email_dir.mkdir(exist_ok=True)
    print("✅ Directory created")
    print()

# List emails
email_files = list(email_dir.glob("*"))

if not email_files:
    print("❌ No emails found!")
    print()
    print("This means:")
    print("  1. No employees have been created yet")
    print("  2. Or email sending is disabled")
    print()
    print("Next step: Create an employee")
    print("  Run: python test_arman_kapil.py")
    print()
else:
    print(f"✅ Found {len(email_files)} email(s)")
    print()

    for email_file in sorted(email_files):
        print(f"📧 {email_file.name}")
        print("-" * 80)

        with open(email_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Show first 500 characters
        if len(content) > 500:
            print(content[:500])
            print("\n... [truncated] ...\n")
        else:
            print(content)

        print()

print("=" * 80)
print("INFORMATION")
print("=" * 80)
print()
print("Email Backend: File-Based")
print("Location: emails/ directory")
print("Format: Text files with email content")
print()
print("This backend:")
print("✅ Works without SMTP configuration")
print("✅ Saves all emails to disk")
print("✅ No internet required")
print("✅ Perfect for testing and debugging")
print()
print("To see email content:")
print("  1. Check the emails/ directory")
print("  2. View .txt files")
print("  3. Should show subject, headers, and body")
print()
