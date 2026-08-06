from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.core.exceptions import ValidationError as DjangoValidationError


def is_platform_admin(user) -> bool:
    return bool(getattr(user, "is_superuser", False) or getattr(user, "role", "") == "SUPERADMIN")


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_authenticated", False) and is_platform_admin(request.user))


class IsTenantAdministrator(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(getattr(request.user, "is_authenticated", False))
        return getattr(request.user, "role", "") in {"ADMIN", "SUPERADMIN"} or getattr(request.user, "is_superuser", False)


class CanOperateDocuments(BasePermission):
    """Viewers are read-only; makers edit; approvers submit/approve; admins can do both."""

    def has_permission(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return False
        if request.method in SAFE_METHODS:
            return True
        role = getattr(request.user, "role", "")
        if getattr(request.user, "is_superuser", False) or role in {"ADMIN", "SUPERADMIN"}:
            return True
        action = getattr(view, "action", None)
        if action in {"submit", "approve"}:
            return role == "APPROVER"
        if action in {"create", "partial_update", "destroy", "validate", "resubmit", "cancel", "inbound", "ap_alias"}:
            return role in {"MAKER", "APPROVER"}
        return role in {"MAKER", "APPROVER"}


class ResolveActiveCompany(BasePermission):
    """
    Resolves the tenant(s) in scope for this request from the X-Company-ID header and stamps
    request.active_company / request.active_company_ids, which TenantQuerysetMixin and every
    view use to filter querysets and stamp new rows.

    Must run as a DRF permission (not Django middleware): request.user is only populated once
    DRF's JWTAuthentication runs inside the view's dispatch(), which happens after Django's
    middleware stack has already finished.

    - Header absent/invalid -> falls back to request.user.company (single tenant).
    - Header = a Company UUID in the user's own company_group -> that one company.
    - Header = "group" -> every company in the user's company_group ("Whole group" dropdown).
    - user.company is None (platform-wide super admin) -> every active company in the system.

    Always returns True; pair with IsAuthenticated to actually gate access.
    """

    def has_permission(self, request, view):
        from apps.company.models import Company

        request.active_company = None
        request.active_company_ids = []

        user = request.user
        if not getattr(user, "is_authenticated", False):
            return True

        own_company = user.company
        header_value = request.headers.get("X-Company-ID")

        if own_company is None and is_platform_admin(user):
            all_companies = Company.objects.filter(is_active=True)
            request.active_company_ids = list(all_companies.values_list("id", flat=True))
            if header_value and header_value != "group":
                try:
                    picked = all_companies.filter(pk=header_value).first()
                except (ValueError, TypeError, DjangoValidationError):
                    picked = all_companies.filter(short_code=header_value).first()
                if picked:
                    request.active_company = picked
                    request.active_company_ids = [picked.id]
            return True

        if own_company is None:
            # A company-less auditor/viewer is not implicitly a platform administrator.
            return True

        group_companies = Company.objects.filter(
            company_group=own_company.company_group_id, is_active=True
        ) if own_company.company_group_id else Company.objects.filter(pk=own_company.pk)

        if header_value == "group":
            request.active_company = own_company
            request.active_company_ids = list(group_companies.values_list("id", flat=True))
        elif header_value:
            try:
                picked = group_companies.filter(pk=header_value).first()
            except (ValueError, TypeError, DjangoValidationError):
                picked = group_companies.filter(short_code=header_value).first()
            if picked:
                request.active_company = picked
                request.active_company_ids = [picked.id]
            else:
                request.active_company = own_company
                request.active_company_ids = [own_company.id]
        else:
            request.active_company = own_company
            request.active_company_ids = [own_company.id]

        return True


def resolve_write_company(request, payload=None):
    """Resolve one tenant for a write or raise a client-facing validation error."""
    from rest_framework.exceptions import ValidationError
    from apps.company.models import Company

    if request.active_company is not None:
        return request.active_company
    if getattr(request.user, "company", None) is not None:
        return request.user.company

    requested = (payload or {}).get("company") or (payload or {}).get("ent")
    allowed = Company.objects.filter(id__in=request.active_company_ids, is_active=True)
    if requested:
        try:
            company = allowed.filter(pk=requested).first()
        except (ValueError, TypeError, DjangoValidationError):
            company = allowed.filter(short_code=requested).first()
        if company:
            return company
        raise ValidationError({"company": ["The selected company is invalid or outside your permitted scope."]})

    if allowed.count() == 1:
        return allowed.first()
    raise ValidationError({"company": ["Select one company before creating tenant-owned data."]})
