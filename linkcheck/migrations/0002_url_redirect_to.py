from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linkcheck', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='url',
            name='redirect_to',
            field=models.CharField(default='', max_length=255),
        ),
    ]
