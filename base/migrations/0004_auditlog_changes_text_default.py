from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("base", "0003_alter_dynamicemailconfiguration_options_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE auditlog_logentry
                ALTER COLUMN changes_text SET DEFAULT '';
            """,
            reverse_sql="""
                ALTER TABLE auditlog_logentry
                ALTER COLUMN changes_text DROP DEFAULT;
            """,
        ),
    ]
