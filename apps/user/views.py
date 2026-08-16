from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.company.models import Company
from apps.company.serializers import EntitySerializer
from apps.config.models import SystemConfig
from apps.config import services as config_services
from apps.utils.permissions import IsTenantAdministrator, ResolveActiveCompany, is_platform_admin, resolve_write_company

from .models import Notification, User
from .serializers import NotificationSerializer, UserAdminSerializer
from apps.utils.openapi import GenericApiSerializer, LoginRequestSerializer, MfaRequestSerializer
from drf_spectacular.utils import extend_schema


MFA_CHALLENGE_SALT = "faturathi.auth.mfa"
MFA_CHALLENGE_MAX_AGE_SECONDS = 300


def _user_payload(user: User) -> dict:
    name = (f"{user.first_name} {user.last_name}".strip()) or user.email.split("@")[0]
    return {
        "id": str(user.id),
        "email": user.email,
        "name": name,
        "role": user.role,
        "branch": user.branch,
        "entityId": user.company.short_code if user.company_id else "ALL",
    }


def _auth_response(user: User) -> Response:
    refresh = RefreshToken.for_user(user)
    return Response({
        "status": "authenticated",
        "user": _user_payload(user),
        "token": str(refresh.access_token),
        "refresh": str(refresh),
    })


class LoginView(APIView):
    """Validate the password, then always require the second-factor OTP."""

    permission_classes = [AllowAny]
    serializer_class = LoginRequestSerializer

    @extend_schema(request=LoginRequestSerializer, responses=GenericApiSerializer)
    def post(self, request):
        email = request.data.get("email", "")
        password = request.data.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is None or not user.is_active:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        config = SystemConfig.objects.filter(company_id=user.company_id).first() if user.company_id else None
        if config and not config.allow_user_logins:
            return Response({"detail": "User portal login is disabled for this company. Contact your administrator."},
                            status=status.HTTP_403_FORBIDDEN)
        challenge = signing.dumps(
            {"user_id": str(user.id), "email": user.email},
            salt=MFA_CHALLENGE_SALT,
            compress=True,
        )
        return Response({
            "mfa_required": True,
            "delivery": "email",
            "email": user.email,
            "mfa_challenge": challenge,
            "expires_in": MFA_CHALLENGE_MAX_AGE_SECONDS,
        })


class MfaVerifyView(APIView):
    """Verify OTP only after a recent, successful password authentication."""

    permission_classes = [AllowAny]
    serializer_class = MfaRequestSerializer

    @extend_schema(request=MfaRequestSerializer, responses=GenericApiSerializer)
    def post(self, request):
        email = request.data.get("email", "")
        otp = str(request.data.get("otp", "")).strip()
        challenge = str(request.data.get("mfa_challenge", "")).strip()
        try:
            challenge_payload = signing.loads(
                challenge,
                salt=MFA_CHALLENGE_SALT,
                max_age=MFA_CHALLENGE_MAX_AGE_SECONDS,
            )
        except (signing.BadSignature, signing.SignatureExpired):
            return Response(
                {"detail": "Your password verification has expired or is invalid. Please sign in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            user = User.objects.get(
                id=challenge_payload.get("user_id"),
                email__iexact=email,
                is_active=True,
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Password verification does not match this user. Please sign in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        config = SystemConfig.objects.filter(company_id=user.company_id).first() if user.company_id else None
        if config and not config.allow_user_logins:
            return Response({"detail": "User portal login is disabled for this company. Contact your administrator."},
                            status=status.HTTP_403_FORBIDDEN)

        if otp != settings.DEMO_MFA_OTP:
            return Response({"detail": f"Invalid 2FA OTP code. Use the demo security code: {settings.DEMO_MFA_OTP}."},
                             status=status.HTTP_401_UNAUTHORIZED)
        return _auth_response(user)


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GenericApiSerializer

    def get(self, request):
        user = request.user
        payload = _user_payload(user)
        payload["mfa_enabled"] = user.mfa_enabled
        payload["company"] = EntitySerializer(user.company).data if user.company_id else None

        group_companies = []
        if user.company_id and user.company.company_group_id:
            group_companies = EntitySerializer(
                Company.objects.filter(company_group_id=user.company.company_group_id, is_active=True),
                many=True,
            ).data
        payload["group_companies"] = group_companies
        return Response(payload)


class UserAdminViewSet(viewsets.ModelViewSet):
    """/api/users — user management within the caller's own company."""

    serializer_class = UserAdminSerializer
    permission_classes = [ResolveActiveCompany, IsTenantAdministrator]

    def get_queryset(self):
        own_company = getattr(self.request.user, "company", None)
        qs = User.objects.all()
        if own_company is not None:
            qs = qs.filter(company=own_company)
        elif not is_platform_admin(self.request.user):
            qs = qs.none()
        return qs.order_by("email")

    def perform_create(self, serializer):
        own_company = getattr(self.request.user, "company", None)
        if own_company is None and not is_platform_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("A tenant company is required to manage users.")
        company = resolve_write_company(self.request, self.request.data)
        serializer.save(company=company)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    def perform_update(self, serializer):
        if serializer.instance == self.request.user and serializer.validated_data.get("is_active") is False:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"is_active": ["You cannot disable your own account."]})
        user = serializer.save(company=serializer.instance.company)
        config_services.log(
            self.request, "USER_ENABLED" if user.is_active else "USER_DISABLED",
            entity="User", entity_id=user.id, target_email=user.email,
        )


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(
            company_id__in=getattr(self.request, "active_company_ids", []), user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            company=resolve_write_company(self.request, self.request.data),
            user=self.request.user, created_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)
