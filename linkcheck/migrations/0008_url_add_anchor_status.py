from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("linkcheck", "0007_url_add_redirect_status_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="url",
            name="anchor_status",
            field=models.BooleanField(null=True),
        ),
    ]
