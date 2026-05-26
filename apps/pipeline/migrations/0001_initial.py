import django.contrib.postgres.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("admin_areas", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="JbaIngestionRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_date", models.DateField()),
                ("forecast_issue_time", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("partial", "Partial"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("files_expected", models.IntegerField(blank=True, null=True)),
                ("files_processed", models.IntegerField(blank=True, null=True)),
                ("csv_blob_url", models.TextField(blank=True, null=True)),
                ("error_log", models.JSONField(blank=True, null=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "JBA Ingestion Run",
                "verbose_name_plural": "JBA Ingestion Runs",
                "ordering": ["-run_date"],
            },
        ),
        migrations.CreateModel(
            name="FloodForecastFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "ingestion_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="forecast_files",
                        to="pipeline.jbaingestionrun",
                    ),
                ),
                ("forecast_issue_date", models.DateField()),
                ("forecast_target_date", models.DateField()),
                ("tiff_blob_url", models.TextField()),
                ("original_filename", models.TextField(blank=True, null=True)),
                ("file_size_bytes", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Flood Forecast File",
                "verbose_name_plural": "Flood Forecast Files",
                "ordering": ["-forecast_issue_date"],
            },
        ),
        migrations.AddConstraint(
            model_name="floodforecastfile",
            constraint=models.UniqueConstraint(
                fields=("forecast_issue_date", "forecast_target_date"),
                name="unique_forecast_issue_target_date",
            ),
        ),
        migrations.CreateModel(
            name="FloodForecastImpact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "forecast_file",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="impacts",
                        to="pipeline.floodforecastfile",
                    ),
                ),
                (
                    "admin_area",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="flood_impacts",
                        to="admin_areas.adminarea",
                    ),
                ),
                ("forecast_issue_date", models.DateField()),
                ("forecast_target_date", models.DateField()),
                ("band_5_mean", models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ("band_5_median", models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ("band_5_p75", models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ("band_5_p90", models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ("band_5_max", models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ("ensembles_nonzero_count", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Flood Forecast Impact",
                "verbose_name_plural": "Flood Forecast Impacts",
                "ordering": ["-forecast_issue_date"],
            },
        ),
        migrations.AddConstraint(
            model_name="floodforecastimpact",
            constraint=models.UniqueConstraint(
                fields=("forecast_issue_date", "forecast_target_date", "admin_area"),
                name="unique_impact_issue_target_admin",
            ),
        ),
        migrations.CreateModel(
            name="ArcRainfallObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("observation_date", models.DateField()),
                (
                    "admin_area",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="arc_observations",
                        to="admin_areas.adminarea",
                    ),
                ),
                ("rainfall_raw", models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ("rainfall", models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ("impact", models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ("event_rp", models.IntegerField(blank=True, null=True)),
                ("cell_trigger", models.BooleanField()),
                ("source_csv_blob_url", models.TextField(blank=True, null=True)),
                ("ingested_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "ARC Rainfall Observation",
                "verbose_name_plural": "ARC Rainfall Observations",
                "ordering": ["-observation_date"],
            },
        ),
        migrations.AddConstraint(
            model_name="arcrainfallobservation",
            constraint=models.UniqueConstraint(
                fields=("observation_date", "admin_area"),
                name="unique_arc_obs_date_admin",
            ),
        ),
        migrations.CreateModel(
            name="ArcTriggerEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trigger_date", models.DateField(unique=True)),
                ("triggered_admin_areas_count", models.IntegerField()),
                (
                    "affected_admin_areas",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.IntegerField(), blank=True, null=True
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending_review", "Pending Review"),
                            ("confirmed", "Confirmed"),
                            ("rejected", "Rejected"),
                            ("sent", "Sent"),
                            ("send_failed", "Send Failed"),
                        ],
                        default="pending_review",
                        max_length=20,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reviewed_trigger_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_notes", models.TextField(blank=True, null=True)),
                ("email_sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "ARC Trigger Event",
                "verbose_name_plural": "ARC Trigger Events",
                "ordering": ["-trigger_date"],
            },
        ),
        migrations.CreateModel(
            name="HdxDataset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dataset_name", models.TextField()),
                ("hdx_url", models.TextField(blank=True, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "file_type",
                    models.CharField(
                        choices=[("geojson", "GeoJSON"), ("csv", "CSV")],
                        max_length=10,
                    ),
                ),
                ("file_blob_url", models.TextField(blank=True, null=True)),
                ("data", models.JSONField(blank=True, null=True)),
                (
                    "loaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="loaded_datasets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("loaded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "HDX Dataset",
                "verbose_name_plural": "HDX Datasets",
                "ordering": ["-loaded_at"],
            },
        ),
    ]
