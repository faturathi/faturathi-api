import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("company", "0003_companygroup_unique"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyBranch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("code", models.CharField(max_length=12)),
                ("name", models.CharField(max_length=120)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(default="Muscat", max_length=60)),
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("contact_phone", models.CharField(blank=True, max_length=20)),
                ("invoice_prefix", models.CharField(default="INV-", max_length=20)),
                ("invoice_suffix", models.CharField(default="/OM", max_length=12)),
                ("credit_note_prefix", models.CharField(default="CN-", max_length=20)),
                ("credit_note_suffix", models.CharField(default="/CN", max_length=12)),
                ("next_invoice_number", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_set", to="company.company")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["company__short_code", "code"]},
        ),
        migrations.AddConstraint(
            model_name="companybranch",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_deleted", False)), fields=("company", "code"),
                name="uniq_active_branch_code_per_company",
            ),
        ),
    ]
