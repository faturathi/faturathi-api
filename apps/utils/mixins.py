class TenantQuerysetMixin:
    """
    ViewSet mixin: scopes the queryset to request.active_company_ids (set by
    core.middleware.ActiveCompanyMiddleware) and stamps company/created_by on create.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(company_id__in=self.request.active_company_ids)

    def perform_create(self, serializer):
        company = self.request.active_company or getattr(self.request.user, "company", None)
        serializer.save(company=company, created_by=self.request.user)
