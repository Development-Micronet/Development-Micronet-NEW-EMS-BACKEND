from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='is_tokenized',
            field=models.BooleanField(default=False, help_text='Grants tokenized API access visibility when True'),
        ),
    ]
