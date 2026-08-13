from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from django.urls import path

from .views import EmailOtpRequestView, LoginView, MeView, MfaVerifyView, NotificationViewSet, UserAdminViewSet

router = DefaultRouter(trailing_slash=False)
router.register("users", UserAdminViewSet, basename="user")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/email-otp", EmailOtpRequestView.as_view(), name="auth-email-otp"),
    path("auth/mfa-verify", MfaVerifyView.as_view(), name="auth-mfa-verify"),
    path("auth/refresh", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me", MeView.as_view(), name="auth-me"),
] + router.urls
