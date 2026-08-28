import hashlib

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiCredential


class ApiKeyAuthentication(BaseAuthentication):
    keyword = "X-API-KEY"

    def authenticate(self, request):
        raw_key = request.headers.get(self.keyword)
        if not raw_key:
            return None
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        credential = ApiCredential.objects.select_related("service_user").filter(
            key_hash=digest, is_active=True, service_user__is_active=True
        ).first()
        if credential is None:
            raise AuthenticationFailed("Invalid or revoked API key.")
        credential.last_used_at = timezone.now()
        credential.save(update_fields=["last_used_at"])
        return credential.service_user, credential
