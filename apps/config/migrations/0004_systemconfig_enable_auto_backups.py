from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("config", "0003_apicredential")]

    operations = [
        migrations.AddField(
            model_name="systemconfig",
            name="enable_auto_backups",
            field=models.BooleanField(default=True),
        ),
    ]
