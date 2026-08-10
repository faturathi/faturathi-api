from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.config.views import ResetSeedsView

# Shared urlconf mounted at both /api/v1/ (current) and /api/ (back-compat alias for existing
# integrations, e.g. faturathi-billing desktop app configs pointing at the old unversioned path).
api_patterns = [
    path("health", lambda request: JsonResponse({"status": "ok"}), name="health"),
    path("schema", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="swagger-ui"),
    path("redoc", SpectacularRedocView.as_view(url_name="openapi-schema"), name="redoc"),

    path("", include("apps.user.urls")),
    path("", include("apps.company.urls")),
    path("", include("apps.documents.urls")),
    path("", include("apps.peppol.urls")),
    path("", include("apps.config.urls")),
    path("", include("apps.reports.urls")),

    # thin aliases (server.ts compatibility, see Addendum v1.1 section B)
    path("reset-db", ResetSeedsView.as_view(), name="reset-db"),
    path("clear", ResetSeedsView.as_view(), name="clear"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_patterns)),
    path("api/", include(api_patterns)),
]
