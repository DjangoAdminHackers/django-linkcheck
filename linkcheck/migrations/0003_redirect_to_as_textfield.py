# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linkcheck', '0002_url_redirect_to'),
    ]

    operations = [
        migrations.AlterField(
            model_name='url',
            name='redirect_to',
            field=models.TextField(blank=True),
        ),
    ]
