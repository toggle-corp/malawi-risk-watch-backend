from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_areas", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="adminarea",
            name="admin_code",
        ),
        migrations.AddField(
            model_name="adminarea",
            name="pcode",
            field=models.CharField(default="", db_index=True, max_length=20, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="adminarea",
            name="ifrc_id",
            field=models.IntegerField(blank=True, db_index=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="adminarea",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="adminarea",
            name="bbox",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="adminarea",
            name="centroid",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
