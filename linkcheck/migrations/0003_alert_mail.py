from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('linkcheck', '0002_url_redirect_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='link',
            name='alert_mail',
            field=models.EmailField(null=True),
        ),
    ]
