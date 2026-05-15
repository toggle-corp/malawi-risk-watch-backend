"""Management command to seed realistic dummy data for local development.

Creates:
  - 3 users (admin, reviewer, viewer)
  - 2 JBA ingestion runs with forecast files and per-district impacts
  - ARC rainfall observations for all districts across 3 dates
  - 3 ARC trigger events (pending, confirmed, rejected)
  - Notification recipients scoped to various admin areas
  - Notification logs for the confirmed event

Safe to re-run: existing objects are skipped or updated via get_or_create / update_or_create.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.models import NotificationLog, NotificationRecipient
from apps.pipeline.models import (
    ArcRainfallObservation,
    ArcTriggerEvent,
    FloodForecastFile,
    FloodForecastImpact,
    HdxDataset,
    IngestionStatus,
    JbaIngestionRun,
    TriggerEventStatus,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Admin area ID constants (PKs already in the database after sync_geo)
# ---------------------------------------------------------------------------

DISTRICT_IDS = list(range(5, 37))  # 5–36 inclusive (32 districts, level 2)
REGION_IDS = [2, 3, 4]  # level 1: Central, Northern, Southern

# Districts grouped roughly by region for realistic recipient scoping
NORTHERN_DISTRICTS = [5, 6, 7, 8, 9]
CENTRAL_DISTRICTS = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
SOUTHERN_DISTRICTS = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36]

# ---------------------------------------------------------------------------
# Realistic band_5 value ranges drawn from the JBA CSV sample
# ---------------------------------------------------------------------------

BAND5_SAMPLES = [
    # (mean, median, p75, p90, max)
    (Decimal("0.00010"), Decimal("0.00000"), Decimal("0.00000"), Decimal("0.00140"), Decimal("0.00350")),
    (Decimal("0.00230"), Decimal("0.00000"), Decimal("0.00100"), Decimal("0.00820"), Decimal("0.02100")),
    (Decimal("0.01540"), Decimal("0.00000"), Decimal("0.00000"), Decimal("0.04200"), Decimal("0.21000")),
    (Decimal("0.05780"), Decimal("0.00000"), Decimal("0.02100"), Decimal("0.18600"), Decimal("0.64000")),
    (Decimal("0.12300"), Decimal("0.03500"), Decimal("0.14900"), Decimal("0.38200"), Decimal("1.02000")),
    (Decimal("0.00000"), Decimal("0.00000"), Decimal("0.00000"), Decimal("0.00000"), Decimal("0.00000")),
    (Decimal("0.33200"), Decimal("0.18400"), Decimal("0.52100"), Decimal("0.84000"), Decimal("2.10000")),
    (Decimal("0.74500"), Decimal("0.52000"), Decimal("1.10000"), Decimal("1.89000"), Decimal("4.20000")),
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

    def handle(self, *args, **options) -> None:
        random.seed(42)

        self._create_users()
        self._create_jba_data()
        self._create_arc_data()
        self._create_recipients()
        self._create_notification_logs()
        self._create_hdx_dataset()

        self.stdout.write(self.style.SUCCESS("Dummy data created successfully."))

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

    def _create_jba_data(self) -> None:
        today = date.today()
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
            issue_date = spec["run_date"]
            run, created = JbaIngestionRun.objects.get_or_create(
                run_date=issue_date,
                defaults={
                    "forecast_issue_time": timezone.now() - timedelta(days=(today - issue_date).days),
                    "status": spec["status"],
                    "files_expected": spec["files_expected"],
                    "files_processed": spec["files_processed"],
                    # One CSV covers all lead times for the run
                    "csv_blob_url": f"https://blob.example.com/jba/{issue_date}/impacts.csv",
                    "completed_at": timezone.now() - timedelta(days=(today - issue_date).days),
                },
            )
            action = "Created" if created else "Skipped"
            self.stdout.write(f"  {action} JBA run: {run.run_date}")
            if not created:
                continue

            # Create one TIFF per lead time (1–10 days)
            for lead_days in range(1, 11):
                target_date = issue_date + timedelta(days=lead_days)
                ff, _ = FloodForecastFile.objects.get_or_create(
                    forecast_issue_date=issue_date,
                    forecast_target_date=target_date,
                    defaults={
                        "ingestion_run": run,
                        "tiff_blob_url": f"https://blob.example.com/jba/{issue_date}/lead{lead_days}.tiff",
                        "original_filename": f"MW_{issue_date}_L{lead_days:02d}.tiff",
                        "file_size_bytes": random.randint(500_000, 5_000_000),
                    },
                )

                # Create per-district impacts
                for district_id in DISTRICT_IDS:
                    sample = random.choice(BAND5_SAMPLES)
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
                            "ensembles_nonzero_count": random.randint(0, 51),
                        },
                    )

            self.stdout.write(f"    → forecast files and impacts created for {run.run_date}")

    # ------------------------------------------------------------------
    # ARC rainfall + trigger events
    # ------------------------------------------------------------------

    def _create_arc_data(self) -> None:
        today = date.today()
        obs_dates = [today - timedelta(days=d) for d in (14, 7, 0)]

        for obs_date in obs_dates:
            for district_id in DISTRICT_IDS:
                rainfall = random.choice(ARC_RAINFALL_SAMPLES)
                cell_trigger = rainfall >= Decimal("25.400")
                ArcRainfallObservation.objects.get_or_create(
                    observation_date=obs_date,
                    admin_area_id=district_id,
                    defaults={
                        "rainfall_raw": rainfall * Decimal("1.05"),
                        "rainfall": rainfall,
                        "impact": rainfall * Decimal("0.42") if rainfall > 0 else Decimal("0"),
                        "event_rp": random.choice([None, 2, 5, 10, 20]) if cell_trigger else None,
                        "cell_trigger": cell_trigger,
                        "source_csv_blob_url": f"https://blob.example.com/arc/{obs_date}.csv",
                    },
                )

        self.stdout.write(f"  ARC observations created for {len(obs_dates)} dates × {len(DISTRICT_IDS)} districts")

        # Trigger events — one per obs date, varying statuses
        reviewer = User.objects.filter(email="reviewer@example.com").first()

        triggered_ids = [d for d in DISTRICT_IDS if d % 3 == 0]  # subset that "triggered"

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

    def _create_recipients(self) -> None:
        admin_user = User.objects.filter(email="admin@example.com").first()
        recipients = [
            dict(
                email="alice@dccm.mw",
                name="Alice Banda",
                organization="DCCM",
                admin_area_ids=NORTHERN_DISTRICTS,
            ),
            dict(
                email="bob@dccm.mw",
                name="Bob Phiri",
                organization="DCCM",
                admin_area_ids=CENTRAL_DISTRICTS,
            ),
            dict(
                email="carol@mrcs.mw",
                name="Carol Mwale",
                organization="MRCS",
                admin_area_ids=SOUTHERN_DISTRICTS,
            ),
            dict(
                email="david@undp.mw",
                name="David Tembo",
                organization="UNDP",
                admin_area_ids=DISTRICT_IDS,  # all districts
            ),
            dict(
                email="inactive@example.com",
                name="Inactive User",
                organization="Test",
                admin_area_ids=DISTRICT_IDS[:5],
            ),
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
