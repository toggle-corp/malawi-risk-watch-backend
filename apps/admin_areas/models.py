import typing

from django.db import models
from django_stubs_ext.db.models.manager import RelatedManager


class AdminArea(models.Model):
    """Malawi administrative boundary reference table.

    Levels (provisional):
        0 = Country
        1 = Region
        2 = District
        3 = Traditional Authority
        4 = Village Cluster / Zone

    The geometry column (GEOMETRY(MultiPolygon, 4326)) is added via RunSQL
    in the migration and is not mapped to a Django field — boundaries will
    be ingested separately once real HDX data is wired up.
    """

    admin_code = models.IntegerField(unique=True)
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
    created_at = models.DateTimeField(auto_now_add=True)

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
