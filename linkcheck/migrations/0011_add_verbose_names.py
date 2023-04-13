import django.db.models.deletion
from django.db import migrations, models

from linkcheck.models import STATUS_CODE_CHOICES


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('linkcheck', '0010_url_add_error_message'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='link',
            options={'verbose_name': 'link', 'verbose_name_plural': 'links'},
        ),
        migrations.AlterModelOptions(
            name='url',
            options={'verbose_name': 'URL', 'verbose_name_plural': 'URLs'},
        ),
        migrations.AlterField(
            model_name='link',
            name='content_type',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='contenttypes.contenttype',
                verbose_name='source model'
            ),
        ),
        migrations.AlterField(
            model_name='link',
            name='field',
            field=models.CharField(max_length=128, verbose_name='field'),
        ),
        migrations.AlterField(
            model_name='link',
            name='ignore',
            field=models.BooleanField(default=False, verbose_name='ignored'),
        ),
        migrations.AlterField(
            model_name='link',
            name='object_id',
            field=models.PositiveIntegerField(verbose_name='source object id'),
        ),
        migrations.AlterField(
            model_name='link',
            name='text',
            field=models.CharField(default='', max_length=256, verbose_name='link text'),
        ),
        migrations.AlterField(
            model_name='link',
            name='url',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='links',
                to='linkcheck.url',
                verbose_name='URL'
            ),
        ),
        migrations.AlterField(
            model_name='url',
            name='anchor_status',
            field=models.BooleanField(null=True, verbose_name='anchor status'),
        ),
        migrations.AlterField(
            model_name='url',
            name='error_message',
            field=models.CharField(blank=True, default='', max_length=1024, verbose_name='error message'),
        ),
        migrations.AlterField(
            model_name='url',
            name='last_checked',
            field=models.DateTimeField(blank=True, null=True, verbose_name='last checked'),
        ),
        migrations.AlterField(
            model_name='url',
            name='message',
            field=models.CharField(blank=True, max_length=1024, null=True, verbose_name='message'),
        ),
        migrations.AlterField(
            model_name='url',
            name='redirect_status_code',
            field=models.IntegerField(choices=STATUS_CODE_CHOICES, null=True, verbose_name='redirect status code'),
        ),
        migrations.AlterField(
            model_name='url',
            name='redirect_to',
            field=models.TextField(blank=True, verbose_name='redirects to'),
        ),
        migrations.AlterField(
            model_name='url',
            name='ssl_status',
            field=models.BooleanField(null=True, verbose_name='SSL status'),
        ),
        migrations.AlterField(
            model_name='url',
            name='status',
            field=models.BooleanField(
                choices=[(True, 'Valid'), (False, 'Invalid'), (None, 'Unchecked')],
                null=True,
                verbose_name='status'
            ),
        ),
        migrations.AlterField(
            model_name='url',
            name='status_code',
            field=models.IntegerField(choices=STATUS_CODE_CHOICES, null=True, verbose_name='status code'),
        ),
        migrations.AlterField(
            model_name='url',
            name='url',
            field=models.CharField(max_length=1024, unique=True, verbose_name='URL'),
        ),
    ]
