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

# Enable AI trading for all users
users = User.objects.all()

print("\n🔄 Enabling AI Trading for all users...")
print("=" * 60)

for user in users:
    user.ai_trading_enabled = True
    user.save()
    print(f"✅ {user.email}: AI Trading ENABLED (Balance: ${user.usd_balance})")

print("=" * 60)
print(f"✅ AI Trading enabled for {users.count()} users!")
print("🤖 Trades will start executing within 12 seconds...")
