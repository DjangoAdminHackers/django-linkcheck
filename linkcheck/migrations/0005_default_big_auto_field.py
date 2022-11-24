from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linkcheck', '0004_remove_url_still_exists'),
    ]

    operations = [
        migrations.AlterField(
            model_name='link',
            name='id',
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
            ),
        ),
        migrations.AlterField(
            model_name='url',
            name='id',
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
            ),
        ),
    ]
