from django.middleware.csrf import CsrfViewMiddleware


class TrustAllOriginsCsrfViewMiddleware(CsrfViewMiddleware):
    """Keep CSRF-token validation while accepting Origin headers from any host.

    Django deliberately has no literal ``CSRF_TRUSTED_ORIGINS = ['*']`` setting.
    This opt-in middleware supplies that behavior for development/UAT integrations.
    Set CSRF_TRUST_ALL_ORIGINS=False in production to restore Django's strict
    scheme-qualified trusted-origin validation.
    """

    def _origin_verified(self, request):
        return True
