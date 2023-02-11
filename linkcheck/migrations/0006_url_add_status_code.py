from django.db import migrations, models

from linkcheck.models import STATUS_CODE_CHOICES


class Migration(migrations.Migration):

    dependencies = [
        ("linkcheck", "0005_default_big_auto_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="url",
            name="status_code",
            field=models.IntegerField(
                choices=STATUS_CODE_CHOICES,
                null=True,
            ),
        ),
    ]
