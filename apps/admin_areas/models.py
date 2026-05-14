import typing

from django.db import models
from django_stubs_ext.db.models.manager import RelatedManager


class AdminArea(models.Model):
    """Malawi administrative boundary reference table.

    Levels:
        0 = Country
        1 = Region
        2 = District
        3 = Traditional Authority  (sourced from HDX, not IFRC)
        4 = Village Cluster / Zone (sourced from HDX, not IFRC)

    External join keys:
        pcode    — humanitarian P-code (e.g. MW, MW1, MW101); primary key
                   used when joining against HDX, OCHA, and ARC datasets.
        ifrc_id  — IFRC GO integer id; used as the upsert key during
                   sync_geo. Null for levels 3–4 which come from HDX.

    PostGIS column added via RunSQL in the initial migration (not mapped as a Django field):
        geometry  — GEOMETRY(MultiPolygon, 4326)  full boundary polygon

    bbox and centroid are stored as raw GeoJSON dicts (JSONField).
    """

    pcode = models.CharField(max_length=20, unique=True, db_index=True)
    ifrc_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    name = models.TextField()
    level = models.IntegerField()
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    country_iso = models.CharField(max_length=10, default="MWI")
    bbox = models.JSONField(null=True, blank=True)
    centroid = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # reverse relation type hints
    children: typing.ClassVar[RelatedManager["AdminArea"]]
    flood_impacts: typing.ClassVar[RelatedManager["apps.pipeline.models.FloodForecastImpact"]]  # type: ignore[name-defined]  # noqa: F821
    arc_observations: typing.ClassVar[RelatedManager["apps.pipeline.models.ArcRainfallObservation"]]  # type: ignore[name-defined]  # noqa: F821

    class Meta:
        verbose_name = "Admin Area"
        verbose_name_plural = "Admin Areas"
        ordering = ["level", "name"]

    @typing.override
    def __str__(self) -> str:
        return f"{self.name} (L{self.level})"
