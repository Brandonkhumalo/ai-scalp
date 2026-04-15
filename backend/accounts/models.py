from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True)
    ai_trading_enabled = models.BooleanField(default=False)
    capital_use_demo = models.BooleanField(
        default=True,
        help_text='Use Capital.com demo account (True) or live account (False).'
    )
    autonomous_trading_enabled = models.BooleanField(default=False, help_text='Enable 24/7 autonomous trading agent that executes trades automatically during market hours')
    ml_bootstrap_mode = models.BooleanField(default=True, help_text='Bootstrap mode: allows AI trading without ML model (uses technical analysis only). Auto-disables once ML model is trained.')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_users')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class BlacklistedToken(models.Model):
    token = models.TextField(unique=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Blacklisted token: {self.token[:20]}..."


class UserRole(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('compliance_officer', 'Compliance Officer'),
        ('trader', 'Trader'),
        ('user', 'User'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user.email} - {self.role}"
