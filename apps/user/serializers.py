from rest_framework import serializers

from .models import Notification, User


class UserAdminSerializer(serializers.ModelSerializer):
    """Matches faturathi-ui's /api/users contract: id, email, role, branch, mfa, status."""

    mfa = serializers.BooleanField(source="mfa_enabled", required=False)
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "role", "branch", "mfa", "status",
                  "designation", "phone", "company", "first_name", "last_name", "password"]
        read_only_fields = ["id", "status"]
        extra_kwargs = {"password": {"write_only": True, "required": False}}

    def get_status(self, obj) -> str:
        return "Active" if obj.is_active else "Disabled"

    def create(self, validated_data):
        password = validated_data.pop("password", None) or User.objects.make_random_password()
        user = User(**validated_data)
        user.set_password(password)
        user.save()
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
