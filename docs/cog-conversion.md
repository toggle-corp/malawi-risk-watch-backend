# COG Conversion

How JBA GeoTIFF files are converted to Cloud-Optimized GeoTIFFs (COGs) before being stored, and how to use the conversion utilities in the ingestion pipeline.

---

## Why COG?

A plain GeoTIFF must be downloaded in full before a client can read any pixels. A COG is internally re-tiled and includes pre-built overview (zoom) levels, so HTTP clients can fetch only the bytes they need for the current viewport using **range requests**.

Mapbox/MapLibre use this to stream flood raster tiles directly from Azure Blob Storage — no tile server required.

---

## Utilities — `apps/pipeline/cog.py`

### `convert_to_cog(input_path, output_path)`

Converts a GeoTIFF on disk to a COG written to `output_path`.

```python
from apps.pipeline.cog import convert_to_cog

convert_to_cog("/tmp/raw_from_jba.tif", "/tmp/converted.tif")
```

- **Compression:** deflate (lossless — flood depth values are preserved exactly)
- **Overview resampling:** bilinear (smooth rendering when zoomed out)
- Input and output can be `str` or `pathlib.Path`
- Output file is overwritten if it already exists

Use this when you already have a file path to write to (e.g. writing to a mounted volume before uploading).

---

### `convert_to_cog_bytes(input_path)`

Converts a GeoTIFF to COG and returns the result as `bytes` — no permanent file is written.

```python
from apps.pipeline.cog import convert_to_cog_bytes

cog_bytes = convert_to_cog_bytes("/tmp/raw_from_jba.tif")
```

Internally writes to a `tempfile`, reads it back as bytes, then deletes the temp file. Use this when you want to pipe the result directly into Django's file storage:

```python
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from apps.pipeline.cog import convert_to_cog_bytes

cog_bytes = convert_to_cog_bytes(raw_tiff_path)
storage_key = default_storage.save(
    f"jba/tiff/{issue_date}/lead{lead_days:02d}.tif",
    ContentFile(cog_bytes),
)
# storage_key is what you store in FloodForecastFile.tiff
```

---

## Integrating into the JBA ingestion pipeline

The ingestion job fetches 10 TIFFs per run from JBA (one per forecast lead day). Each TIFF must be converted to COG **before** being saved to Azure Blob Storage. The `FloodForecastFile.tiff` field is a Django `FileField` — it stores the storage key (blob path), not a URL.

The pipeline step for each TIFF should look like this:

```python
import tempfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.pipeline.cog import convert_to_cog_bytes
from apps.pipeline.models import FloodForecastFile, JbaIngestionRun


def ingest_tiff(
    run: JbaIngestionRun,
    raw_tiff_bytes: bytes,
    issue_date,
    target_date,
    lead_days: int,
    original_filename: str,
) -> FloodForecastFile:
    # Write the raw bytes to a temp file so rasterio can open it
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp.write(raw_tiff_bytes)
        tmp_path = Path(tmp.name)

    try:
        cog_bytes = convert_to_cog_bytes(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    storage_key = default_storage.save(
        f"jba/tiff/{issue_date}/lead{lead_days:02d}.tif",
        ContentFile(cog_bytes),
    )

    return FloodForecastFile.objects.create(
        ingestion_run=run,
        forecast_issue_date=issue_date,
        forecast_target_date=target_date,
        tiff=storage_key,
        original_filename=original_filename,
        file_size_bytes=len(cog_bytes),
    )
```

Key points:

- `convert_to_cog_bytes` requires a file path, not raw bytes — write to a `tempfile` first, then clean it up.
- Pass the returned `storage_key` (not a URL) to `FloodForecastFile.tiff`. Django generates the URL from the key at query time.
- `file_size_bytes` should record the COG size (post-conversion), not the original.
- The storage key pattern `jba/tiff/{issue_date}/lead{lead_days:02d}.tif` matches the `upload_to="jba/tiff/"` set on the `FileField`.

---

## Serving

| Environment | How range requests are handled |
|---|---|
| Dev | `RangeRequestMiddleware` in `utils/middleware.py` (active when `DEBUG=True`) |
| Prod | Azure Blob Storage handles range requests natively |

The GraphQL `tiff` field on `FloodForecastFileType` returns a `DjangoFileType` object with `name`, `size`, and `url`. The `url` is what Mapbox/MapLibre uses to fetch the COG.
