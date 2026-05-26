from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pipeline", "0001_initial"),
    ]

    operations = [
        # JbaIngestionRun: csv_blob_url → csv (TextField → FileField)
        migrations.RenameField("jbaingestionrun", "csv_blob_url", "csv"),
        migrations.AlterField(
            model_name="jbaingestionrun",
            name="csv",
            field=models.FileField(blank=True, null=True, upload_to="jba/csv/"),
        ),
        # FloodForecastFile: tiff_blob_url → tiff (TextField → FileField)
        migrations.RenameField("floodforecastfile", "tiff_blob_url", "tiff"),
        migrations.AlterField(
            model_name="floodforecastfile",
            name="tiff",
            field=models.FileField(upload_to="jba/tiff/"),
        ),
        # ArcRainfallObservation: source_csv_blob_url → source_csv (TextField → FileField)
        migrations.RenameField("arcrainfallobservation", "source_csv_blob_url", "source_csv"),
        migrations.AlterField(
            model_name="arcrainfallobservation",
            name="source_csv",
            field=models.FileField(blank=True, null=True, upload_to="arc/csv/"),
        ),
        # HdxDataset: file_blob_url → file (TextField → FileField)
        migrations.RenameField("hdxdataset", "file_blob_url", "file"),
        migrations.AlterField(
            model_name="hdxdataset",
            name="file",
            field=models.FileField(blank=True, null=True, upload_to="hdx/"),
        ),
    ]
