import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("company", "0004_companybranch"),
        ("documents", "0003_document_document_type_document_extra_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="branch",
            field=models.ForeignKey(
                blank=True,
                help_text="Operational branch/outlet; shares the document company's VATIN.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documents",
                to="company.companybranch",
            ),
        ),
    ]
