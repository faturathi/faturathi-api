from django.db import migrations, models


def protect_existing_group_keys(apps, schema_editor):
    CompanyGroup = apps.get_model("company", "CompanyGroup")
    used_names, used_vatins = set(), set()
    for group in CompanyGroup._base_manager.filter(is_deleted=False).order_by("created_at", "id"):
        name_key = group.name.strip().casefold()
        vat_key = group.group_vatin.strip().upper()
        updates = {}
        if name_key not in used_names:
            updates["normalized_name"] = name_key
            used_names.add(name_key)
        if vat_key not in used_vatins:
            updates["normalized_vatin"] = vat_key
            used_vatins.add(vat_key)
        if updates:
            CompanyGroup._base_manager.filter(pk=group.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [("company", "0002_initial")]
    operations = [
        migrations.AddField(model_name="companygroup", name="normalized_name", field=models.CharField(blank=True, editable=False, max_length=120, null=True, unique=True)),
        migrations.AddField(model_name="companygroup", name="normalized_vatin", field=models.CharField(blank=True, editable=False, max_length=14, null=True, unique=True)),
        migrations.RunPython(protect_existing_group_keys, migrations.RunPython.noop),
    ]
