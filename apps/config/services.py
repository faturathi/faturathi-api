from .models import SystemLog


def log(request, action: str, entity: str = "", entity_id="", **detail):
    """Write an immutable SystemLog row. Call from every mutating endpoint."""
    company = getattr(request, "active_company", None) or getattr(request.user, "company", None)
    if company is None:
        return None
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    return SystemLog.objects.create(
        company=company,
        user=user,
        action=action,
        entity=entity,
        entity_id=str(entity_id or ""),
        detail=detail,
        ip_address=request.META.get("REMOTE_ADDR"),
        created_by=user,
    )
