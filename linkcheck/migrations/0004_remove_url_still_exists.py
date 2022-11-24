from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('linkcheck', '0003_redirect_to_as_textfield'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='url',
            name='still_exists',
        ),
    ]
