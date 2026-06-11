"""Resolve geographic points to admin areas.

Reverse-geocoding: given a list of (lat, lon) points, resolve each to
the AdminArea PK whose PostGIS geometry contains the point.

Strategy
--------
Build a single VALUES-based SQL query so we hit the DB in one round-trip
per pipeline run.  The deepest matching admin level (≤ target_level) wins.
Points that fall outside all known boundaries resolve to None and are
silently dropped by the transform phase.
"""

import logging

from django.db import connection

logger = logging.getLogger(__name__)


def resolve_admin_areas(
    coords: list[tuple[float, float]],
    *,
    target_level: int = 3,
) -> dict[tuple[float, float], list[int]]:
    """Resolve a list of (lat, lon) tuples to all matching AdminArea PKs.

    Returns
    -------
    dict mapping (lat, lon) → list of AdminArea PKs (empty list if unresolvable).

    """
    if not coords:
        return {}

    values_sql = ", ".join(f"({lat!r}, {lon!r}, {i})" for i, (lat, lon) in enumerate(coords))

    sql = f"""
        SELECT i.lat, i.lon, aa.id AS admin_id
        FROM (VALUES {values_sql}) AS i(lat, lon, idx)
        JOIN admin_areas_adminarea aa
          ON ST_Contains(
                 ST_SetSRID(ST_GeomFromGeoJSON(aa.bbox::text), 4326),
                 ST_SetSRID(ST_MakePoint(i.lon, i.lat), 4326)
             )
        WHERE aa.level <= {target_level}
    """

    result: dict[tuple[float, float], list[int]] = {c: [] for c in coords}

    with connection.cursor() as cur:
        cur.execute(sql)
        for lat, lon, admin_id in cur.fetchall():
            result[(float(lat), float(lon))].append(admin_id)

    resolved = sum(1 for v in result.values() if v)
    logger.info(
        "Resolved %d/%d coordinate pairs to admin areas (level ≤ %d).",
        resolved,
        len(coords),
        target_level,
    )
    return result
