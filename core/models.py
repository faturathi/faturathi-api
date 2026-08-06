import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class BaseModel(models.Model):
    """Audit base: UUID pk, timestamps, created_by, soft delete."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+")
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()      # default: hides deleted
    all_objects = models.Manager()     # includes deleted

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])


class TenantModel(BaseModel):
    """Row-level isolation: every business row belongs to one Company (tenant)."""

    company = models.ForeignKey(
        "company.Company", on_delete=models.CASCADE,
        related_name="%(class)s_set", db_index=True)

    class Meta(BaseModel.Meta):
        abstract = True
