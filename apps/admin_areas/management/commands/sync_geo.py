"""Sync Malawi administrative areas (levels 0–2) from the IFRC GO API.

Usage
-----
    ./manage.py sync_geo
    ./manage.py sync_geo --dry-run   # fetch and log, but roll back DB writes

What it does
------------
Upserts AdminArea rows for admin0 (country), admin1 (region), and admin2
(district) by calling three IFRC GO REST endpoints. Records are keyed on
ifrc_id so the command is safe to re-run — existing rows are updated in
place, new rows are inserted.

bbox and centroid are stored as raw GeoJSON dicts (JSONField). Admin1
centroid is derived from the bbox center (midpoint of the bbox coordinates)
because the district endpoint doesn't return a centroid.

Repointing to another country
------------------------------
Change COUNTRY_IFRC_ID, COUNTRY_ISO3, and COUNTRY_PCODE to match the target
country. Then rebuild ADMIN1_PCODE_BY_IFRC_ID by calling:

    GET /api/v2/district/?country=<new_id>

and matching the returned district names/ids against the HDX P-code list for
that country. The command will raise a clear error if an IFRC id appears that
isn't in the mapping — use that to catch any gaps before production runs.
"""

import typing
from collections.abc import Iterator
from typing import Any

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.admin_areas.models import AdminArea

# ---------------------------------------------------------------------------
# Configuration — change these to repoint at a different country
# ---------------------------------------------------------------------------

COUNTRY_IFRC_ID = 110  # Malawi
COUNTRY_ISO3 = "MWI"
COUNTRY_PCODE = "MW"

# IFRC doesn't return P-codes for admin0/admin1, so map them explicitly.
# Keys are IFRC GO district ids; values are HDX-standard P-codes.
ADMIN1_PCODE_BY_IFRC_ID: dict[int, str] = {
    2063: "MW1",  # Northern Region
    2062: "MW2",  # Central Region
    2064: "MW3",  # Southern Region
}

GO_DOMAIN = "https://goadmin-stage.ifrc.org"
HTTP_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "Sync Malawi administrative areas (levels 0–2) from IFRC GO."

    @typing.override
    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch data and log what would happen, but roll back all DB writes.",
        )

    @typing.override
    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run mode — changes will be rolled back."))

        syncer = GeoSyncer(stdout=self.stdout, style=self.style)
        syncer.run(dry_run=dry_run)


# ---------------------------------------------------------------------------
# Syncer
# ---------------------------------------------------------------------------


class GeoSyncer:
    def __init__(self, stdout: Any, style: Any) -> None:
        self.stdout = stdout
        self.style = style
        self._counts: dict[int, dict[str, int]] = {
            0: {"created": 0, "updated": 0},
            1: {"created": 0, "updated": 0},
            2: {"created": 0, "updated": 0},
        }

    def run(self, dry_run: bool = False) -> None:
        with transaction.atomic():
            self.sync_admin0()
            self.sync_admin1s()
            self.sync_admin2s()

            self._print_summary()

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run complete — transaction rolled back."))

    # ------------------------------------------------------------------
    # Level sync methods
    # ------------------------------------------------------------------

    def sync_admin0(self) -> AdminArea:
        url = f"{GO_DOMAIN}/api/v2/country/{COUNTRY_IFRC_ID}/"
        self.stdout.write(f"Fetching admin0 from {url}")

        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        area, created = AdminArea.objects.update_or_create(
            ifrc_id=COUNTRY_IFRC_ID,
            defaults={
                "pcode": COUNTRY_PCODE,
                "name": data["name"],
                "level": 0,
                "parent": None,
                "country_iso": COUNTRY_ISO3,
                "bbox": data.get("bbox") or None,
                "centroid": None,  # Admin0 has no centroid in the API
            },
        )
        self._log(area, created)
        self._counts[0]["created" if created else "updated"] += 1
        return area

    def sync_admin1s(self) -> list[AdminArea]:
        url = f"{GO_DOMAIN}/api/v2/district/?country={COUNTRY_IFRC_ID}"
        country = AdminArea.objects.get(ifrc_id=COUNTRY_IFRC_ID)
        areas: list[AdminArea] = []

        for record in self._paginate(url):
            ifrc_id: int = record["id"]

            if ifrc_id not in ADMIN1_PCODE_BY_IFRC_ID:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipping unmapped admin1 ifrc_id={ifrc_id} "
                        f"(name={record.get('name')!r}) — add to ADMIN1_PCODE_BY_IFRC_ID to include it.",
                    ),
                )
                continue

            pcode = ADMIN1_PCODE_BY_IFRC_ID[ifrc_id]
            bbox = record.get("bbox") or None
            # District endpoint has no centroid — derive from bbox center
            centroid = self._centroid_from_bbox(bbox)

            area, created = AdminArea.objects.update_or_create(
                ifrc_id=ifrc_id,
                defaults={
                    "pcode": pcode,
                    "name": record["name"],
                    "level": 1,
                    "parent": country,
                    "country_iso": COUNTRY_ISO3,
                    "bbox": bbox,
                    "centroid": centroid,
                },
            )
            self._log(area, created)
            self._counts[1]["created" if created else "updated"] += 1
            areas.append(area)

        return areas

    def sync_admin2s(self) -> list[AdminArea]:
        url = f"{GO_DOMAIN}/api/v2/admin2/?admin1__country={COUNTRY_IFRC_ID}"
        admin1_by_ifrc_id = {
            a.ifrc_id: a for a in AdminArea.objects.filter(level=1, country_iso=COUNTRY_ISO3) if a.ifrc_id is not None
        }
        areas: list[AdminArea] = []

        for record in self._paginate(url):
            ifrc_id: int = record["id"]
            pcode: str = record["code"]
            parent_ifrc_id: int = record["district_id"]

            parent = admin1_by_ifrc_id.get(parent_ifrc_id)
            if parent is None:
                raise ValueError(
                    f"Admin2 {pcode!r} (ifrc_id={ifrc_id}) references unknown "
                    f"parent district_id={parent_ifrc_id}. Run sync_geo again after "
                    "admin1 sync is complete, or check ADMIN1_PCODE_BY_IFRC_ID.",
                )

            area, created = AdminArea.objects.update_or_create(
                ifrc_id=ifrc_id,
                defaults={
                    "pcode": pcode,
                    "name": record["name"],
                    "level": 2,
                    "parent": parent,
                    "country_iso": COUNTRY_ISO3,
                    "bbox": record.get("bbox") or None,
                    "centroid": record.get("centroid") or None,
                },
            )
            self._log(area, created)
            self._counts[2]["created" if created else "updated"] += 1
            areas.append(area)

        return areas

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _paginate(self, url: str) -> Iterator[dict]:
        """Follow IFRC GO pagination until next is null."""
        next_url: str | None = url
        while next_url:
            resp = requests.get(next_url, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            yield from data["results"]
            next_url = data.get("next")

    def _centroid_from_bbox(self, bbox: dict | None) -> dict | None:
        """Derive a GeoJSON Point centroid from a GeoJSON Polygon bbox."""
        if not bbox:
            return None
        try:
            coords = bbox["coordinates"][0]  # exterior ring
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            return {
                "type": "Point",
                "coordinates": [
                    (min(lons) + max(lons)) / 2,
                    (min(lats) + max(lats)) / 2,
                ],
            }
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  Could not derive centroid from bbox: {exc}"))
            return None

    def _log(self, area: AdminArea, created: bool) -> None:
        verb = "Created" if created else "Updated"
        self.stdout.write(f"  {verb} L{area.level} {area.pcode!r:12s} {area.name}")

    def _print_summary(self) -> None:
        self.stdout.write(self.style.SUCCESS("\nSync complete:"))
        for level, counts in self._counts.items():
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Level {level}: {counts['created']} created, {counts['updated']} updated",
                ),
            )
