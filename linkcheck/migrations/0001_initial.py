# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Link',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('object_id', models.PositiveIntegerField()),
                ('field', models.CharField(max_length=128)),
                ('text', models.CharField(default='', max_length=256)),
                ('ignore', models.BooleanField(default=False)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Url',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('url', models.CharField(unique=True, max_length=255)),
                ('last_checked', models.DateTimeField(null=True, blank=True)),
                ('status', models.BooleanField(null=True)),
                ('message', models.CharField(max_length=1024, null=True, blank=True)),
                ('still_exists', models.BooleanField(default=False)),
            ],
        ),
        migrations.AddField(
            model_name='link',
            name='url',
            field=models.ForeignKey(related_name='links', to='linkcheck.Url', on_delete=models.CASCADE),
        ),
    ]
