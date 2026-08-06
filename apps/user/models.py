import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TenantModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "SUPERADMIN")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = [
        ("SUPERADMIN", "Super Admin"), ("ADMIN", "Admin"), ("MAKER", "Maker"),
        ("APPROVER", "Approver"), ("VIEWER", "Viewer"),
    ]

    username = None  # login is by email
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    company = models.ForeignKey(
        "company.Company", null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default="VIEWER")
    designation = models.CharField(max_length=80, blank=True)
    branch = models.CharField(max_length=80, blank=True)  # free-text office label, e.g. "HQ Muscat"
    phone = models.CharField(max_length=20, blank=True)
    mfa_enabled = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Notification(TenantModel):
    LEVEL_CHOICES = [("INFO", "Info"), ("WARNING", "Warning"), ("ERROR", "Error")]

    user = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=140)
    message = models.TextField(blank=True)
    level = models.CharField(max_length=8, choices=LEVEL_CHOICES, default="INFO")
    is_read = models.BooleanField(default=False)
