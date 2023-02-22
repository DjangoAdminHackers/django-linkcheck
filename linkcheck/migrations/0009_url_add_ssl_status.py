from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("linkcheck", "0008_url_add_anchor_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="url",
            name="ssl_status",
            field=models.BooleanField(null=True),
        ),
    ]
