from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("employee", "0001_add_is_tokenized"),
        ("employee", "0005_employee_role"),
    ]

    operations = [
        # This is an empty merge migration that resolves the two conflicting
        # migration heads. Running `migrate` after adding this file will mark
        # both branches as merged.
    ]
