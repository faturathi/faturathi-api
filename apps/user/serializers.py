from rest_framework import serializers
import secrets

from .models import Notification, User


class UserAdminSerializer(serializers.ModelSerializer):
    """Matches faturathi-ui's /api/users contract: id, email, role, branch, mfa, status."""

    mfa = serializers.BooleanField(source="mfa_enabled", required=False)
    status = serializers.SerializerMethodField()
    temporaryPassword = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "role", "branch", "mfa", "status", "temporaryPassword",
                  "designation", "phone", "company", "first_name", "last_name", "password", "is_active"]
        read_only_fields = ["id", "status"]
        extra_kwargs = {"password": {"write_only": True, "required": False}}

    def get_status(self, obj) -> str:
        return "Active" if obj.is_active else "Disabled"

    def get_temporaryPassword(self, obj):
        return getattr(obj, "_temporary_password", None)

    def create(self, validated_data):
        supplied_password = validated_data.pop("password", None)
        password = supplied_password or secrets.token_urlsafe(12)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if not supplied_password:
            user._temporary_password = password
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user", "title", "message", "level", "is_read", "created_at"]
        read_only_fields = ["id", "created_at"]
