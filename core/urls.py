from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.config.views import ResetSeedsView

urlpatterns = [
    path("api/health", lambda request: JsonResponse({"status": "ok"}), name="health"),
    path("api/schema", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="swagger-ui"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="openapi-schema"), name="redoc"),
    path("admin/", admin.site.urls),

    path("api/", include("apps.user.urls")),
    path("api/", include("apps.company.urls")),
    path("api/", include("apps.documents.urls")),
    path("api/", include("apps.peppol.urls")),
    path("api/", include("apps.config.urls")),
    path("api/", include("apps.reports.urls")),

    # thin aliases (server.ts compatibility, see Addendum v1.1 section B)
    path("api/reset-db", ResetSeedsView.as_view(), name="reset-db"),
    path("api/clear", ResetSeedsView.as_view(), name="clear"),
]
