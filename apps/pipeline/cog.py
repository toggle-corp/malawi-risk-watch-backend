"""Cloud-Optimized GeoTIFF (COG) conversion utilities."""

import tempfile
from pathlib import Path

from osgeo import gdal

gdal.UseExceptions()  # turn GDAL errors into Python exceptions instead of silent failures


def convert_to_cog(input_path: str | Path, output_path: str | Path) -> None:
    """Convert a GeoTIFF to a Cloud-Optimized GeoTIFF (COG) at output_path.

    Tiled to the Web Mercator (EPSG:3857) GoogleMapsCompatible scheme so MapLibre/
    Mapbox can consume tiles directly with no reprojection at read time.

    Uses deflate compression (lossless — safe for flood depth values).
    Cubic resampling for both the reprojection-to-grid and overview steps gives
    smooth rendering at all zoom levels (avoids the blur from nearest-neighbour).
    """
    gdal.Translate(
        str(output_path),
        str(input_path),
        format="COG",
        creationOptions=[
            "TILING_SCHEME=GoogleMapsCompatible",  # reproject + tile to Web Mercator grid
            "WARP_RESAMPLING=CUBIC",               # resampling for the reprojection-to-grid step
            "OVERVIEW_RESAMPLING=CUBIC",           # resampling for the overview pyramids
            "COMPRESS=DEFLATE",                    # lossless — preserves exact depth values
            "PREDICTOR=YES",                       # better deflate ratio on continuous float data
            "BIGTIFF=IF_SAFER",
        ],
    )


def convert_to_cog_bytes(input_path: str | Path) -> bytes:
    """Convert a GeoTIFF to COG and return the result as bytes.

    Useful for saving directly to Django file storage without a permanent
    intermediate file on disk.
    """
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        convert_to_cog(input_path, tmp_path)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
