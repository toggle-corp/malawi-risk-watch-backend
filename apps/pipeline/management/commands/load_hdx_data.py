"""Management command to load HDX risk assessment datasets for Malawi.

Fetches each CSV from the HEIGiT public storage, uploads it to Django's
configured file storage (Azure Blob in prod, local media in dev), and records
the resulting URL in HdxDataset.file_blob_url. Safe to re-run — existing
records are updated in place and the stored file is overwritten.

Source: https://data.humdata.org/dataset/malawi---risk-assessment-indicators
Dataset validity: 13 October 2025 – 13 April 2026

Usage:
    docker compose exec web python manage.py load_hdx_data
    docker compose exec web python manage.py load_hdx_data --user admin@example.com
"""

import typing
import urllib.request
from argparse import ArgumentParser
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from apps.pipeline.models import HdxDataset
from apps.users.models import User

BASE_URL = "https://hot.storage.heigit.org/heigit-hdx-public/risk_assessment_inputs/mwi"
STORAGE_PREFIX = "hdx"

DATASETS = [
    dict(
        name="MWI_ADM2_rural_population",
        url=f"{BASE_URL}/MWI_ADM2_rural_population.csv",
        description=(
            "Rural population breakdown per ADM2 district: female population, children under 5, "
            "elderly, population under 15, and rural population percentage."
        ),
    ),
    dict(
        name="MWI_ADM2_access",
        url=f"{BASE_URL}/MWI_ADM2_access.csv",
        description=(
            "Population accessibility indicators per ADM2: population within 5/10/20km of "
            "educational facilities and within 30min/1hr/2hr of hospitals and primary healthcare."
        ),
    ),
    dict(
        name="MWI_ADM2_demographics",
        url=f"{BASE_URL}/MWI_ADM2_demographics.csv",
        description=(
            "Total population demographics per ADM2: female population, children under 5, "
            "female under 5, elderly (65+), population under 15, and female under 15."
        ),
    ),
    dict(
        name="MWI_ADM2_facilities",
        url=f"{BASE_URL}/MWI_ADM2_facilities.csv",
        description="Number of hospitals per ADM2 district.",
    ),
    dict(
        name="MWI_ADM2_vulnerability",
        url=f"{BASE_URL}/MWI_ADM2_vulnerability.csv",
        description=(
            "Vulnerable population counts per ADM2: female, children under 5, elderly (65+), "
            "population under 15, and rural sub-breakdowns with rural population percentage."
        ),
    ),
    dict(
        name="MWI_ADM2_flood_exposure",
        url=f"{BASE_URL}/MWI_ADM2_flood_exposure.csv",
        description=(
            "Flood exposure per ADM2 at return periods 10/50/100/500 years (30cm depth): "
            "exposed population groups, educational institutions, hospitals, and primary healthcare "
            "facilities (counts and percentages)."
        ),
    ),
]


class Command(BaseCommand):
    help = "Load HDX risk assessment CSV datasets into file storage and record them in the database."

    @typing.override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--user",
            dest="user_email",
            default=None,
            help="Email of the user to set as loaded_by (defaults to first superuser).",
        )

    @typing.override
    def handle(self, *args: Any, **options: Any) -> None:
        user = self._resolve_user(options["user_email"])

        for spec in DATASETS:
            self.stdout.write(f"  Fetching {spec['name']} …")
            try:
                raw = self._fetch(spec["url"])
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"    Failed to fetch: {exc}"))
                continue

            storage_path = f"{STORAGE_PREFIX}/{spec['name']}.csv"
            try:
                if default_storage.exists(storage_path):
                    default_storage.delete(storage_path)
                saved_path = default_storage.save(storage_path, ContentFile(raw))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"    Failed to save to storage: {exc}"))
                continue

            obj, created = HdxDataset.objects.update_or_create(
                dataset_name=spec["name"],
                defaults={
                    "hdx_url": spec["url"],
                    "description": spec["description"],
                    "file_type": "csv",
                    "file": saved_path,
                    "data": None,
                    "loaded_by": user,
                },
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"    {action}: {obj.dataset_name} → {saved_path}"))

    def _resolve_user(self, email: str | None):
        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist as exc:
                raise CommandError(f"User with email '{email}' not found.") from exc
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if not user:
            raise CommandError("No superuser found. Pass --user <email> or create a superuser first.")
        return user

    def _fetch(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
            return response.read()
