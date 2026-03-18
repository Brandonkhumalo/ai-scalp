from rest_framework import serializers
from .models import User, UserRole


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['role', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    """Read-only serializer for user data in API responses."""
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'full_name', 'phone',
            'ai_trading_enabled', 'autonomous_trading_enabled',
            'ml_bootstrap_mode', 'approval_status', 'roles',
        ]
        read_only_fields = fields

    def get_roles(self, obj):
        return list(obj.roles.values_list('role', flat=True))


class UserProfileSerializer(serializers.ModelSerializer):
    """Minimal serializer for profile endpoint."""
    user_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = User
        fields = ['user_id', 'email', 'full_name', 'phone']
        read_only_fields = fields
