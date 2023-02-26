from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linkcheck', '0009_url_add_ssl_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='url',
            name='error_message',
            field=models.CharField(blank=True, default='', max_length=1024),
        ),
    ]
