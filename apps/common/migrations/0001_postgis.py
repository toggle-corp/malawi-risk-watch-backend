from django.db import migrations


class Migration(migrations.Migration):
    """Enable the PostGIS extension.

    Must run before any migration that adds geometry columns.
    Requires the PostgreSQL user to have CREATE EXTENSION privileges
    (superuser or the pg_extension_owner role on Azure Flexible Server).
    """

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS postgis;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
