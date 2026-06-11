"""Cloud-Optimized GeoTIFF (COG) conversion utilities."""

import subprocess
import tempfile
from pathlib import Path


def convert_to_cog(input_path: str | Path, output_path: str | Path) -> None:
    """Convert a GeoTIFF to a Cloud-Optimized GeoTIFF (COG) at output_path.

    Tiled to the Web Mercator (EPSG:3857) GoogleMapsCompatible scheme so MapLibre/
    Mapbox can consume tiles directly with no reprojection at read time.

    Uses deflate compression (lossless — safe for flood depth values).
    Cubic resampling for both the reprojection-to-grid and overview steps gives
    smooth rendering at all zoom levels (avoids the blur from nearest-neighbour).

    Requires gdal-bin to be installed (gdal_translate on PATH).
    In Docker this comes from the gdal-bin apt package.
    """
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "gdal_translate",
            "-of",
            "COG",
            "-co",
            "TILING_SCHEME=GoogleMapsCompatible",
            "-co",
            "WARP_RESAMPLING=CUBIC",
            "-co",
            "OVERVIEW_RESAMPLING=CUBIC",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "PREDICTOR=YES",
            "-co",
            "BIGTIFF=IF_SAFER",
            str(input_path),
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


# Left this for compatibility. TODO: Delete this
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


def convert_to_cog_bytes_from_bytes(input_bytes: bytes) -> bytes:
    """Convert in-memory GeoTIFF bytes to COG and return the result as bytes.

    Writes the input to a temporary file, runs COG conversion, and returns
    the output as bytes — useful for saving directly to Django file storage
    without retaining any files on disk.
    """
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_input:
        tmp_input_path = Path(tmp_input.name)
        tmp_input.write(input_bytes)

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_out:
        tmp_out_path = Path(tmp_out.name)

    try:
        convert_to_cog(tmp_input_path, tmp_out_path)
        return tmp_out_path.read_bytes()
    finally:
        tmp_input_path.unlink(missing_ok=True)
        tmp_out_path.unlink(missing_ok=True)
