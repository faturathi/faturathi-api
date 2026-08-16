from rest_framework import serializers


class GenericApiSerializer(serializers.Serializer):
    status = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)
    message = serializers.CharField(required=False)


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class MfaRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(write_only=True)
    mfa_challenge = serializers.CharField(write_only=True)


class DocumentTypeSerializer(serializers.Serializer):
    key = serializers.CharField()
    code = serializers.CharField()
    label = serializers.CharField()
    sublabel = serializers.CharField()
    is_b2c = serializers.BooleanField()
    direction_hint = serializers.CharField()
