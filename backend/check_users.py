#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, '/home/runner/workspace/backend')
os.environ.setdefault('DJANGO_SECRET_KEY', 'dev-secret-key')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_platform.settings')

django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
users = User.objects.all()

print("\n📊 Current User Status:")
print("=" * 60)
for user in users:
    print(f"Email: {user.email}")
    print(f"  AI Trading: {'✅ ENABLED' if user.ai_trading_enabled else '❌ DISABLED'}")
    print(f"  Balance: ${user.usd_balance}")
    print("-" * 60)

print(f"\nTotal Users: {users.count()}")
print(f"AI Enabled: {users.filter(ai_trading_enabled=True).count()}")
