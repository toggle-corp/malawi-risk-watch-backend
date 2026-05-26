"""Cloud-Optimized GeoTIFF (COG) conversion utilities."""

import tempfile
from pathlib import Path

from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles


def convert_to_cog(input_path: str | Path, output_path: str | Path) -> None:
    """Convert a GeoTIFF to a Cloud-Optimized GeoTIFF (COG) in-place at output_path.

    Uses deflate compression (lossless — safe for flood depth values).
    Bilinear resampling for overviews gives smooth rendering at lower zoom levels.
    """
    cog_translate(
        str(input_path),
        str(output_path),
        cog_profiles.get("deflate"),
        overview_resampling="bilinear",
        quiet=True,
    )


def convert_to_cog_bytes(input_path: str | Path) -> bytes:
    """Convert a GeoTIFF to COG and return the result as bytes.

    Useful for saving directly to Django file storage without a permanent
    intermediate file on disk.
    """
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=True) as tmp:
        tmp_path = Path(tmp.name)

    try:
        convert_to_cog(input_path, tmp_path)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
