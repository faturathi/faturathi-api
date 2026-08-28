import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("company", "0004_companybranch"),
    ]

    operations = [
        migrations.AlterField(
            model_name="company",
            name="company_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="companies",
                to="company.companygroup",
            ),
        ),
    ]
