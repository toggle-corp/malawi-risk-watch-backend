"""Management command to seed realistic dummy data for local development.

Creates:
  - Malawi administrative hierarchy (country → 3 regions → 28 districts)
  - 3 users (admin, reviewer, viewer)
  - 2 JBA ingestion runs with forecast files and per-district impacts
  - ARC rainfall observations for all districts across 3 dates
  - 3 ARC trigger events (pending, confirmed, rejected)
  - Notification recipients scoped to various admin areas
  - Notification logs for the confirmed event

Safe to re-run: existing objects are skipped or updated via get_or_create / update_or_create.
"""

import random
import typing
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.admin_areas.models import AdminArea
from apps.notifications.models import NotificationLog, NotificationRecipient
from apps.pipeline.cog import convert_to_cog_bytes
from apps.pipeline.models import (
    ArcIngestionRun,
    ArcRainfallObservation,
    ArcTriggerEvent,
    FloodForecastFile,
    FloodForecastImpact,
    HdxDataset,
    IngestionStatus,
    JbaIngestionRun,
    TriggerEventStatus,
)
from apps.users.models import User

DUMMY_TIFF = Path(__file__).resolve().parents[4] / "dummy" / "dummy.tif"

# ---------------------------------------------------------------------------
# Malawi administrative hierarchy
# ---------------------------------------------------------------------------

MALAWI_REGIONS = [
    {"pcode": "MW1", "name": "Northern Region", "ifrc_id": 1},
    {"pcode": "MW2", "name": "Central Region", "ifrc_id": 2},
    {"pcode": "MW3", "name": "Southern Region", "ifrc_id": 3},
]

# (pcode, name, region_pcode) — 28 official Malawi districts
MALAWI_DISTRICTS = [
    # Northern
    ("MW101", "Chitipa", "MW1"),
    ("MW102", "Karonga", "MW1"),
    ("MW103", "Likoma", "MW1"),
    ("MW104", "Mzimba", "MW1"),
    ("MW105", "Nkhata Bay", "MW1"),
    ("MW106", "Rumphi", "MW1"),
    # Central
    ("MW201", "Dedza", "MW2"),
    ("MW202", "Dowa", "MW2"),
    ("MW203", "Kasungu", "MW2"),
    ("MW204", "Lilongwe", "MW2"),
    ("MW205", "Mchinji", "MW2"),
    ("MW206", "Nkhotakota", "MW2"),
    ("MW207", "Ntcheu", "MW2"),
    ("MW208", "Ntchisi", "MW2"),
    ("MW209", "Salima", "MW2"),
    # Southern
    ("MW301", "Balaka", "MW3"),
    ("MW302", "Blantyre", "MW3"),
    ("MW303", "Chikwawa", "MW3"),
    ("MW304", "Chiradzulu", "MW3"),
    ("MW305", "Machinga", "MW3"),
    ("MW306", "Mangochi", "MW3"),
    ("MW307", "Mulanje", "MW3"),
    ("MW308", "Mwanza", "MW3"),
    ("MW309", "Neno", "MW3"),
    ("MW310", "Nsanje", "MW3"),
    ("MW311", "Phalombe", "MW3"),
    ("MW312", "Thyolo", "MW3"),
    ("MW313", "Zomba", "MW3"),
]

# ---------------------------------------------------------------------------
# Realistic band_5 value ranges — people affected; always whole numbers in 100s/1000s
# ---------------------------------------------------------------------------

BAND5_SAMPLES = [
    # (mean, median, p75, p90, max)
    (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")),
    (Decimal("100"), Decimal("0"), Decimal("0"), Decimal("200"), Decimal("500")),
    (Decimal("200"), Decimal("0"), Decimal("100"), Decimal("400"), Decimal("900")),
    (Decimal("500"), Decimal("0"), Decimal("200"), Decimal("800"), Decimal("1800")),
    (Decimal("800"), Decimal("300"), Decimal("600"), Decimal("1400"), Decimal("3200")),
    (Decimal("1200"), Decimal("700"), Decimal("1500"), Decimal("2700"), Decimal("5500")),
    (Decimal("2500"), Decimal("1800"), Decimal("3100"), Decimal("5000"), Decimal("9600")),
    (Decimal("4800"), Decimal("3500"), Decimal("6200"), Decimal("9400"), Decimal("18000")),
]

# Realistic ARC rainfall values (mm) — sampled from the CSV
ARC_RAINFALL_SAMPLES = [
    Decimal("0.000"),
    Decimal("2.540"),
    Decimal("5.080"),
    Decimal("7.620"),
    Decimal("10.160"),
    Decimal("12.700"),
    Decimal("15.240"),
    Decimal("20.320"),
    Decimal("25.400"),
    Decimal("38.100"),
    Decimal("50.800"),
]


class Command(BaseCommand):
    help = "Seed realistic dummy data for local development."

    @typing.override
    def handle(self, *args: Any, **options: Any) -> None:
        random.seed(42)

        district_ids, northern_ids, central_ids, southern_ids = self._create_admin_areas()
        self._create_users()
        self._create_jba_data(district_ids)
        self._create_arc_data(district_ids, northern_ids, central_ids, southern_ids)
        self._create_recipients(district_ids, northern_ids, central_ids, southern_ids)
        self._create_notification_logs()
        self._create_hdx_dataset()

        self.stdout.write(self.style.SUCCESS("Dummy data created successfully."))

    # ------------------------------------------------------------------
    # Admin areas
    # ------------------------------------------------------------------

    def _create_admin_areas(self) -> tuple[list[int], list[int], list[int], list[int]]:
        country, _ = AdminArea.objects.get_or_create(
            pcode="MW",
            defaults={"name": "Malawi", "level": 0},
        )

        region_objs: dict[str, AdminArea] = {}
        for r in MALAWI_REGIONS:
            pcode = typing.cast("str", r["pcode"])
            obj, _ = AdminArea.objects.get_or_create(
                pcode=pcode,
                defaults={"name": r["name"], "level": 1, "parent": country, "ifrc_id": r["ifrc_id"]},
            )
            region_objs[pcode] = obj

        northern_ids, central_ids, southern_ids = [], [], []
        for pcode, name, region_pcode in MALAWI_DISTRICTS:
            obj, _ = AdminArea.objects.get_or_create(
                pcode=pcode,
                defaults={"name": name, "level": 2, "parent": region_objs[region_pcode]},
            )
            if region_pcode == "MW1":
                northern_ids.append(obj.pk)
            elif region_pcode == "MW2":
                central_ids.append(obj.pk)
            else:
                southern_ids.append(obj.pk)

        all_ids = northern_ids + central_ids + southern_ids
        self.stdout.write(f"  Admin areas ready: 1 country, 3 regions, {len(all_ids)} districts")
        return all_ids, northern_ids, central_ids, southern_ids

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def _create_users(self) -> None:
        users = [
            dict(email="admin@example.com", name="Admin User", role="admin", is_staff=True, is_superuser=True),
            dict(email="reviewer@example.com", name="Reviewer User", role="reviewer", is_staff=True, is_superuser=False),
            dict(email="viewer@example.com", name="Viewer User", role="viewer", is_staff=False, is_superuser=False),
        ]
        for u in users:
            obj, created = User.objects.get_or_create(
                email=u["email"],
                defaults={
                    "name": u["name"],
                    "role": u["role"],
                    "is_staff": u["is_staff"],
                    "is_superuser": u["is_superuser"],
                },
            )
            if created:
                obj.set_password("password123")
                obj.save(update_fields=["password"])
                self.stdout.write(f"  Created user: {obj.email}")
            else:
                self.stdout.write(f"  Skipped user: {obj.email} (already exists)")

    # ------------------------------------------------------------------
    # JBA ingestion data
    # ------------------------------------------------------------------

    def _get_dummy_cog_path(self, storage_key: str) -> str:
        if default_storage.exists(storage_key):
            return storage_key
        cog_bytes = convert_to_cog_bytes(DUMMY_TIFF)
        return default_storage.save(storage_key, ContentFile(cog_bytes))

    def _create_jba_data(self, district_ids: list[int]) -> None:
        today = date.today()
        self.stdout.write("  Converting dummy TIFF to COG …")
        runs_spec = [
            dict(
                run_date=today - timedelta(days=7),
                status=IngestionStatus.SUCCESS,
                files_expected=10,
                files_processed=10,
            ),
            dict(
                run_date=today - timedelta(days=1),
                status=IngestionStatus.SUCCESS,
                files_expected=10,
                files_processed=10,
            ),
        ]

        for spec in runs_spec:
            issue_date = typing.cast("date", spec["run_date"])
            run, created = JbaIngestionRun.objects.get_or_create(
                run_date=issue_date,
                defaults={
                    "forecast_issue_time": timezone.now() - timedelta(days=(today - issue_date).days),
                    "status": spec["status"],
                    "files_expected": spec["files_expected"],
                    "files_processed": spec["files_processed"],
                    "csv": f"jba/csv/{issue_date}/impacts.csv",
                    "completed_at": timezone.now() - timedelta(days=(today - issue_date).days),
                },
            )
            action = "Created" if created else "Skipped"
            self.stdout.write(f"  {action} JBA run: {run.run_date}")
            if not created:
                continue

            for lead_days in range(1, 11):
                target_date = issue_date + timedelta(days=lead_days)
                storage_key = f"jba/tiff/{issue_date}/lead{lead_days:02d}.tif"
                cog_path = self._get_dummy_cog_path(storage_key)
                ff, _ = FloodForecastFile.objects.get_or_create(
                    forecast_issue_date=issue_date,
                    forecast_target_date=target_date,
                    defaults={
                        "ingestion_run": run,
                        "tiff": cog_path,
                        "original_filename": f"MW_{issue_date}_L{lead_days:02d}.tif",
                        "file_size_bytes": random.randint(500_000, 5_000_000),  # noqa: S311
                    },
                )

                for district_id in district_ids:
                    sample = random.choice(BAND5_SAMPLES)  # noqa: S311
                    FloodForecastImpact.objects.get_or_create(
                        forecast_issue_date=issue_date,
                        forecast_target_date=target_date,
                        admin_area_id=district_id,
                        defaults={
                            "forecast_file": ff,
                            "band_5_mean": sample[0],
                            "band_5_median": sample[1],
                            "band_5_p75": sample[2],
                            "band_5_p90": sample[3],
                            "band_5_max": sample[4],
                            "ensembles_nonzero_count": random.randint(0, 51),  # noqa: S311
                        },
                    )

            self.stdout.write(f"    → forecast files and impacts created for {run.run_date}")

    # ------------------------------------------------------------------
    # ARC rainfall + trigger events
    # ------------------------------------------------------------------

    def _create_arc_data(
        self,
        district_ids: list[int],
        northern_ids: list[int],
        central_ids: list[int],
        southern_ids: list[int],
    ) -> None:
        today = date.today()
        obs_dates = [today - timedelta(days=d) for d in (14, 7, 0)]

        for obs_date in obs_dates:
            run, created = ArcIngestionRun.objects.get_or_create(
                run_date=obs_date,
                defaults={
                    "status": IngestionStatus.SUCCESS,
                    "rows_expected": len(district_ids),
                    "rows_processed": len(district_ids),
                    "source_csv": f"arc/csv/{obs_date}.csv",
                    "completed_at": timezone.now() - timedelta(days=(today - obs_date).days),
                },
            )
            action = "Created" if created else "Skipped"
            self.stdout.write(f"  {action} ARC run: {run.run_date}")

            for district_id in district_ids:
                rainfall = random.choice(ARC_RAINFALL_SAMPLES)  # noqa: S311
                cell_trigger = rainfall >= Decimal("25.400")
                ArcRainfallObservation.objects.get_or_create(
                    observation_date=obs_date,
                    admin_area_id=district_id,
                    defaults={
                        "ingestion_run": run,
                        "rainfall_raw": rainfall * Decimal("1.05"),
                        "rainfall": rainfall,
                        "impact": Decimal(round(int(rainfall * 42), -2)) if rainfall > 0 else Decimal("0"),
                        "event_rp": random.choice([None, 2, 5, 10, 20]) if cell_trigger else None,  # noqa: S311
                        "cell_trigger": cell_trigger,
                    },
                )

        self.stdout.write(f"  ARC observations created for {len(obs_dates)} dates × {len(district_ids)} districts")

        reviewer = User.objects.filter(email="reviewer@example.com").first()
        triggered_ids = [d for d in district_ids if district_ids.index(d) % 3 == 0]

        events_spec = [
            dict(
                trigger_date=today - timedelta(days=14),
                status=TriggerEventStatus.REJECTED,
                reviewed_by=reviewer,
                reviewed_at=timezone.now() - timedelta(days=13),
                review_notes="False positive — seasonal baseline exceeded, no real risk.",
            ),
            dict(
                trigger_date=today - timedelta(days=7),
                status=TriggerEventStatus.CONFIRMED,
                reviewed_by=reviewer,
                reviewed_at=timezone.now() - timedelta(days=6),
                review_notes="Confirmed after cross-checking JBA forecasts.",
            ),
            dict(
                trigger_date=today,
                status=TriggerEventStatus.PENDING_REVIEW,
                reviewed_by=None,
                reviewed_at=None,
                review_notes=None,
            ),
        ]

        for spec in events_spec:
            ArcTriggerEvent.objects.update_or_create(
                trigger_date=spec["trigger_date"],
                defaults={
                    "triggered_admin_areas_count": len(triggered_ids),
                    "affected_admin_areas": triggered_ids,
                    "status": spec["status"],
                    "reviewed_by": spec["reviewed_by"],
                    "reviewed_at": spec["reviewed_at"],
                    "review_notes": spec["review_notes"],
                },
            )
            self.stdout.write(f"  Trigger event: {spec['trigger_date']} [{spec['status']}]")

    # ------------------------------------------------------------------
    # Notification recipients
    # ------------------------------------------------------------------

    def _create_recipients(
        self,
        district_ids: list[int],
        northern_ids: list[int],
        central_ids: list[int],
        southern_ids: list[int],
    ) -> None:
        admin_user = User.objects.filter(email="admin@example.com").first()
        recipients = [
            dict(email="alice@dccm.mw", name="Alice Banda", organization="DCCM", admin_area_ids=northern_ids),
            dict(email="bob@dccm.mw", name="Bob Phiri", organization="DCCM", admin_area_ids=central_ids),
            dict(email="carol@mrcs.mw", name="Carol Mwale", organization="MRCS", admin_area_ids=southern_ids),
            dict(email="david@undp.mw", name="David Tembo", organization="UNDP", admin_area_ids=district_ids),
            dict(email="inactive@example.com", name="Inactive User", organization="Test", admin_area_ids=district_ids[:5]),
        ]
        for r in recipients:
            obj, created = NotificationRecipient.objects.get_or_create(
                email=r["email"],
                defaults={
                    "name": r["name"],
                    "organization": r["organization"],
                    "admin_area_ids": r["admin_area_ids"],
                    "is_active": r["email"] != "inactive@example.com",
                    "added_by": admin_user,
                },
            )
            action = "Created" if created else "Skipped"
            self.stdout.write(f"  {action} recipient: {obj.email}")

    # ------------------------------------------------------------------
    # Notification logs (for the confirmed event)
    # ------------------------------------------------------------------

    def _create_notification_logs(self) -> None:
        today = date.today()
        confirmed_event = ArcTriggerEvent.objects.filter(
            trigger_date=today - timedelta(days=7),
            status=TriggerEventStatus.CONFIRMED,
        ).first()
        if not confirmed_event:
            self.stdout.write(self.style.WARNING("  Skipping notification logs — confirmed event not found."))
            return

        affected = set(confirmed_event.affected_admin_areas or [])
        recipients = NotificationRecipient.objects.filter(
            is_active=True,
            admin_area_ids__overlap=list(affected),
        )

        for recipient in recipients:
            NotificationLog.objects.get_or_create(
                trigger_event=confirmed_event,
                recipient_email=recipient.email,
                defaults={
                    "recipient": recipient,
                    "status": "sent",
                    "provider_message_id": f"msg_{recipient.email.split('@')[0]}_abc123",
                },
            )
            self.stdout.write(f"  Notification log: {recipient.email}")

    # ------------------------------------------------------------------
    # HDX dataset stub
    # ------------------------------------------------------------------

    def _create_hdx_dataset(self) -> None:
        admin_user = User.objects.filter(email="admin@example.com").first()
        HdxDataset.objects.get_or_create(
            dataset_name="Malawi Administrative Boundaries",
            defaults={
                "hdx_url": "https://data.humdata.org/dataset/cod-ab-mwi",
                "description": "OCHA COD administrative boundaries for Malawi (levels 0–3).",
                "file_type": "geojson",
                "loaded_by": admin_user,
                "data": None,
            },
        )
        self.stdout.write("  HDX dataset stub created.")
