from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("company", "0003_companygroup_unique"), ("config", "0004_systemconfig_enable_auto_backups"), ("user", "0001_initial")]
    operations = [
        migrations.AddField(model_name="systemconfig", name="notification_emails", field=models.JSONField(blank=True, default=list)),
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)), ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("subject", models.CharField(max_length=160)),
                ("category", models.CharField(choices=[("TECHNICAL", "Technical"), ("BILLING", "Billing"), ("PEPPOL", "Peppol / OTA"), ("DATA", "Data / archive")], default="TECHNICAL", max_length=20)),
                ("contact_email", models.EmailField(max_length=254)), ("message", models.TextField()),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("IN_PROGRESS", "In progress"), ("RESOLVED", "Resolved")], default="OPEN", max_length=20)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_set", to="company.company")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="user.user")),
            ], options={"ordering": ["-created_at"]},
        ),
    ]
