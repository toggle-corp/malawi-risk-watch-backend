import io
import logging
import re
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import IO

import paramiko
import polars as pl
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from apps.admin_areas.models import AdminArea
from apps.pipeline.models import FloodForecastFile, FloodForecastImpact, JbaIngestionRun

logger = logging.getLogger(__name__)


class JBAPipeline:
    def __init__(self, jba_ingestion_run: JbaIngestionRun):
        self.jba_ingestion_run = jba_ingestion_run

    tiff_file_pattern = re.compile(
        r"^for_mwi_ts_"
        r"fe(?P<forecast_target>\d{8})T0000Z_"
        r"rd(?P<forecast_issue>\d{8})T0000Z_"
        r"ensAgreement_band05\.tif$",
    )

    csv_file_pattern = re.compile(
        r"for_mwi_ts_rd(?P<issue_date>\d{8})T\d{4}Z_population_impacts\.csv\.zip$",
    )

    @contextmanager
    def connect_sftp_client(self, sftp_url: str, sftp_port: int):
        transport = None
        sftp = None
        try:
            transport = paramiko.Transport((sftp_url, sftp_port))
            transport.connect(
                username=settings.JBA_SFTP_USERNAME,
                password=settings.JBA_SFTP_PASSWORD,
            )
            sftp = paramiko.SFTPClient.from_transport(transport)
            if sftp is None:
                raise RuntimeError("Failed to create SFTP client")

            yield sftp

        except paramiko.AuthenticationException:
            logger.error("Authentication failed")
            raise
        except paramiko.SSHException as e:
            logger.error("SFTP connection failed: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            raise
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()

    def _build_impacts(
        self,
        agg_df: pl.DataFrame,
        issue_date: date,
        forecast_file_hash_map: dict,
        admin_areas: dict,
    ) -> list[FloodForecastImpact]:
        impacts = []

        for row in agg_df.iter_rows(named=True):
            admin_area = admin_areas.get(row["admin_code"])
            if not admin_area:
                raise ValueError(
                    f"AdminArea not found for code: {row['admin_code']} (Issue Date: {issue_date})",
                )

            forecast_file = forecast_file_hash_map.get(row["target_date"])
            if not forecast_file:
                raise ValueError(f"Forecast file not found for date: {row['target_date']}")

            impacts.append(
                FloodForecastImpact(
                    forecast_file=forecast_file,
                    admin_area=admin_area,
                    forecast_issue_date=issue_date,
                    forecast_target_date=row["target_date"],
                    band_5_mean=row["band_5_mean"],
                    band_5_median=row["band_5_median"],
                    band_5_p75=row["band_5_p75"],
                    band_5_p90=row["band_5_p90"],
                    band_5_max=row["band_5_max"],
                    ensembles_nonzero_count=row["ensembles_nonzero_count"],
                ),
            )

        return impacts

    def _parse_csv(self, csv_file: IO[bytes]) -> pl.DataFrame:
        csv_bytes = csv_file.read()
        text_stream = io.TextIOWrapper(io.BytesIO(csv_bytes), encoding="utf-8")

        header1 = next(text_stream).strip().split(",")
        header2 = next(text_stream).strip().split(",")

        if len(header1) != len(header2):
            raise ValueError(
                f"Header row length mismatch: {len(header1)} vs {len(header2)}",
            )

        columns = []
        for h1, h2 in zip(header1, header2, strict=True):
            head1, head2 = h1.strip(), h2.strip()
            columns.append(head1 if not head2 else f"{head1}__{head2}")

        df = pl.read_csv(
            io.BytesIO(csv_bytes),
            skip_rows=2,
            has_header=False,
            new_columns=columns,
        )

        band5_cols = [c for c in df.columns if c.startswith("band_5__")]
        long_df = df.unpivot(
            index=["admin_code", "ensemble"],
            on=band5_cols,
            variable_name="forecast",
            value_name="value",
        )
        long_df = long_df.with_columns(
            pl.col("forecast").str.split("__").list.get(1).str.strptime(pl.Date, "%Y-%m-%d").alias("target_date"),
        )

        return (
            long_df.group_by(["admin_code", "target_date"])
            .agg(
                [
                    pl.col("value").mean().alias("band_5_mean"),
                    pl.col("value").median().alias("band_5_median"),
                    pl.col("value").quantile(0.75).alias("band_5_p75"),
                    pl.col("value").quantile(0.90).alias("band_5_p90"),
                    pl.col("value").max().alias("band_5_max"),
                    (pl.col("value") > 0).sum().alias("ensembles_nonzero_count"),
                ],
            )
            .sort(["admin_code", "target_date"])
        )

    def _process_zip(
        self,
        zip_bytes: io.BytesIO,
        issue_date: date,
        forecast_file_hash_map: dict,
        admin_areas: dict,
    ) -> list[FloodForecastImpact]:
        impacts = []

        with zipfile.ZipFile(zip_bytes) as z:
            for member in z.infolist():
                logger.info("Processing CSV: %s", member.filename)

                with z.open(member) as csv_file:
                    agg_df = self._parse_csv(csv_file)

                impacts.extend(
                    self._build_impacts(agg_df, issue_date, forecast_file_hash_map, admin_areas),
                )

        return impacts

    @staticmethod
    def get_admin_area(admin2_code: str, admin_areas: dict[str, AdminArea]) -> AdminArea | None:
        return admin_areas.get(admin2_code)

    def _collect_impacts(
        self,
        sftp: paramiko.SFTPClient,
        forecast_file_hash_map: dict,
    ) -> list[FloodForecastImpact]:
        admin_areas = {aa.pcode: aa for aa in AdminArea.objects.all()}

        parent_time = self.jba_ingestion_run.run_date - timedelta(days=3)
        impact_path = parent_time.strftime("./mwi/impacts/%Y/%m/%d")

        try:
            files = sftp.listdir(impact_path)
        except FileNotFoundError:
            logger.warning("Impact path not found: %s", impact_path)
            return []

        all_impacts = []

        for filename in files:
            if not filename.endswith(".zip"):
                continue

            match = self.csv_file_pattern.match(filename)
            if not match:
                continue

            issue_date = datetime.strptime(match.group("issue_date"), "%Y%m%d").date()
            remote_zip_path = f"{impact_path}/{filename}"

            logger.info("Processing ZIP: %s", remote_zip_path)

            # No try/except — any failure here aborts the whole pipeline
            with sftp.open(remote_zip_path, "rb") as remote_file:
                zip_bytes = io.BytesIO(remote_file.read())

            self.jba_ingestion_run.csv.save(filename, ContentFile(zip_bytes.getvalue()))
            zip_bytes.seek(0)

            impacts = self._process_zip(zip_bytes, issue_date, forecast_file_hash_map, admin_areas)
            all_impacts.extend(impacts)

        return all_impacts

    def _collect_raster_files(self, sftp: paramiko.SFTPClient) -> list[FloodForecastFile]:
        parent_time = self.jba_ingestion_run.run_date - timedelta(days=3)
        path = parent_time.strftime("./mwi/raster/%Y/%m/%d")

        try:
            tiff_remote_files = sftp.listdir(path)
            logger.info("Found %d tiff files in %s", len(tiff_remote_files), path)
        except FileNotFoundError:
            logger.warning("Raster path not found: %s", path)
            return []

        forecast_files = []

        for tiff_file in tiff_remote_files:
            match = self.tiff_file_pattern.match(tiff_file)
            if not match:
                continue

            forecast_target_date = datetime.strptime(match.group("forecast_target"), "%Y%m%d").date()
            forecast_issue_date = datetime.strptime(match.group("forecast_issue"), "%Y%m%d").date()
            remote_path = f"{path}/{tiff_file}"

            logger.info(
                "Reading raster file=%s target_date=%s issue_date=%s",
                tiff_file,
                forecast_target_date,
                forecast_issue_date,
            )

            with sftp.open(remote_path) as f:
                content = f.read()

            forecast_files.append(
                FloodForecastFile(
                    forecast_issue_date=forecast_issue_date,
                    forecast_target_date=forecast_target_date,
                    tiff=ContentFile(content, name=tiff_file),
                    ingestion_run=self.jba_ingestion_run,
                    original_filename=tiff_file,
                ),
            )

        return forecast_files

    def _collect_all_data(self) -> tuple[list[FloodForecastFile], list[FloodForecastImpact]]:
        with self.connect_sftp_client(settings.JBA_SFTP_URL, settings.JBA_SFTP_PORT) as sftp:
            forecast_files = self._collect_raster_files(sftp)

            forecast_file_hash_map = {f.forecast_target_date: f for f in forecast_files}

            impacts = self._collect_impacts(sftp, forecast_file_hash_map)

        return forecast_files, impacts

    @transaction.atomic()
    def _write_all(
        self,
        forecast_files: list[FloodForecastFile],
        impacts: list[FloodForecastImpact],
    ):
        for ff in forecast_files:
            ff.save()

        FloodForecastImpact.objects.bulk_create(impacts, batch_size=1000)

    def run(self):
        logger.info(
            "Starting JBA pipeline run_id=%s run_date=%s",
            self.jba_ingestion_run.id,
            self.jba_ingestion_run.run_date,
        )

        forecast_files, impacts = self._collect_all_data()

        self._write_all(forecast_files, impacts)

        logger.info("Completed JBA pipeline run_id=%s", self.jba_ingestion_run.id)
