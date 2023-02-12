from django.db import migrations, models

from linkcheck.models import STATUS_CODE_CHOICES


class Migration(migrations.Migration):

    dependencies = [
        ("linkcheck", "0006_url_add_status_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="url",
            name="redirect_status_code",
            field=models.IntegerField(
                choices=STATUS_CODE_CHOICES,
                null=True,
            ),
        ),
    ]
