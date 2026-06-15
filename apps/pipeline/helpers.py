"""Helpers for ingestion pipelines.

Kept separate from the pipeline class because they are pure functions
with no dependency on ingestion run state — easy to unit-test in
isolation and reusable if a second ARC variant appears.
"""

import polars as pl


def coerce_cell_trigger(df: pl.DataFrame) -> pl.DataFrame:
    """Normalise cell_trigger to Boolean regardless of source representation.

    Source sends mixed representations:
      - String:  "False", "True", "false", "true"
      - Integer: 0, 1
      - Boolean: already correct
    """
    col = df["cell_trigger"]

    if col.dtype == pl.Boolean:
        return df

    if col.dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8):
        return df.with_columns(pl.col("cell_trigger").cast(pl.Boolean))

    # String path — handles "False", "TRUE", "1", "yes", etc.
    return df.with_columns(
        pl.col("cell_trigger")
        .cast(pl.Utf8)
        .str.to_uppercase()
        .str.strip_chars()
        .is_in(["TRUE", "1", "YES", "T"])
        .alias("cell_trigger"),
    )


def coerce_event_rp(df: pl.DataFrame) -> pl.DataFrame:
    """Replace event_rp == 0 with null.

    Source sends 0 when no return period is triggered.
    Valid non-null values are 2, 5, 10, 20.
    """
    return df.with_columns(
        pl.when(pl.col("event_rp").cast(pl.Float64, strict=False) == 0)
        .then(None)
        .otherwise(pl.col("event_rp").cast(pl.Float64, strict=False))
        .alias("event_rp"),
    )
