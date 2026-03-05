#!/usr/bin/env python
"""
Check available users in database
"""

import os
import sys

import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")
django.setup()

from django.contrib.auth.models import User

print("Available users in database:")
users = User.objects.all()
for user in users:
    print(f"  - {user.username} (ID: {user.id}, Email: {user.email})")

if not users.exists():
    print("  No users found!")
