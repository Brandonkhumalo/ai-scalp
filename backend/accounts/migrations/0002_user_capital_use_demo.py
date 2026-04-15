from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='capital_use_demo',
            field=models.BooleanField(
                default=True,
                help_text='Use Capital.com demo account (True) or live account (False).',
            ),
        ),
    ]
