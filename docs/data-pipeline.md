# Data Pipeline

How raw data from JBA and ARC is ingested, transformed, and stored — and how it drives the notification workflow.

---

## Overview

```
JBA API                              ARC API
  │                                    │
  ▼                                    ▼
10 TIFF files + 1 CSV per day    Daily rainfall grid per admin area
  │                                    │
  ▼                                    ▼
Azure Blob Storage               Azure Blob Storage
  │                                    │
  ▼                                    ▼
JbaIngestionRun                  ArcRainfallObservation
FloodForecastFile (×10)               │
FloodForecastImpact              [cell_trigger threshold check]
                                       │
                                       ▼
                               ArcTriggerEvent (PENDING_REVIEW)
                                       │
                               [MRCS staff review]
                                       │
                           ┌───────────┴───────────┐
                           ▼                       ▼
                       CONFIRMED               REJECTED
                           │
                   [Celery sends emails]
                           │
                   NotificationLog (per recipient)
                           │
                    status → SENT / SEND_FAILED
```

---

## JBA flood forecast

JBA delivers a daily batch of flood forecast files:

- **10 TIFF files** — one per lead time (day 1 through day 10). Each is a 51-member ensemble raster covering Malawi.
- **1 CSV file** — covers all lead times for that run. Contains pre-aggregated `band_5` ensemble statistics per admin area.

### Models

**`JbaIngestionRun`** — one record per daily fetch job.

| Field | Notes |
|---|---|
| `run_date` | The calendar date of the fetch |
| `forecast_issue_time` | When JBA issued the forecast |
| `status` | `pending` → `running` → `success` / `failed` / `partial` |
| `files_expected` / `files_processed` | Expected 10 TIFFs; tracks partial failures |
| `csv_blob_url` | Azure Blob URL of the single daily CSV (all lead times) |
| `error_log` | JSON array of per-file error details on partial runs |

**`FloodForecastFile`** — one record per TIFF (10 per run).

| Field | Notes |
|---|---|
| `ingestion_run` | FK → `JbaIngestionRun` |
| `forecast_issue_date` | Date the forecast was issued |
| `forecast_target_date` | Date being forecast |
| `tiff_blob_url` | Azure Blob URL of this lead-time TIFF |
| `original_filename` | Filename as received from JBA |

> `lead_time_days` is never stored — always computed as `forecast_target_date - forecast_issue_date`.

**`FloodForecastImpact`** — ensemble-aggregated `band_5` stats, one row per admin area per (issue date, target date) pair. Values are parsed from the single daily CSV.

| Field | Notes |
|---|---|
| `forecast_file` | FK → the matching `FloodForecastFile` for this lead time |
| `admin_area` | FK → `AdminArea` |
| `forecast_issue_date` / `forecast_target_date` | Denormalised for efficient filtering |
| `band_5_mean/median/p75/p90/max` | Flood impact metrics across the 51 ensemble members |
| `ensembles_nonzero_count` | How many of the 51 members predicted non-zero flood impact |

Raw ensemble values (all 51 members) are **not** stored in the database. The CSV in Blob Storage is the authoritative record.

---

## ARC parametric rainfall

ARC delivers daily rainfall observations gridded to Malawi admin boundaries. The ingestion process spatially aggregates grid cells to district level and writes one row per admin area.

### Models

**`ArcRainfallObservation`** — one row per admin area per observation date.

| Field | Notes |
|---|---|
| `observation_date` | Date of the rainfall measurement |
| `admin_area` | FK → `AdminArea` |
| `rainfall_raw` | Raw value from the ARC source (mm) |
| `rainfall` | Bias-corrected / normalised value (mm) |
| `impact` | Derived impact metric (`rainfall × factor`) |
| `event_rp` | Return period estimate (2, 5, 10, or 20 years) when triggered; `NULL` otherwise |
| `cell_trigger` | `TRUE` when `rainfall` meets or exceeds the threshold — name preserved from the JBA source CSV for traceability |
| `source_csv_blob_url` | Azure Blob URL of the raw daily CSV for audit |

**`ArcTriggerEvent`** — created when one or more admin areas exceed the threshold on a given date.

| Field | Notes |
|---|---|
| `trigger_date` | The observation date that tripped the threshold (unique) |
| `triggered_admin_areas_count` | Number of areas that triggered |
| `affected_admin_areas` | `ArrayField(IntegerField)` of `AdminArea` PKs that triggered |
| `status` | Workflow state (see below) |
| `reviewed_by` / `reviewed_at` / `review_notes` | Set when MRCS staff action the event |
| `email_sent_at` | Timestamp when the notification batch completed |

### Trigger event workflow

```
PENDING_REVIEW  →  CONFIRMED  →  SENT
                │              └─ SEND_FAILED (partial / all failed)
                └─ REJECTED
```

1. **PENDING_REVIEW** — created automatically when `cell_trigger = TRUE` for any admin area.
2. **CONFIRMED** — MRCS staff confirm via the admin review page; a Celery task is dispatched immediately.
3. **REJECTED** — staff reject; no emails are sent, event is closed.
4. **SENT / SEND_FAILED** — set by the Celery task after attempting delivery to all matched recipients.

---

## Notifications

On confirmation the Celery task (`send_arc_trigger_notifications`) runs:

1. Queries `NotificationRecipient` where `admin_area_ids` **overlaps** `ArcTriggerEvent.affected_admin_areas`.
2. Renders an email with: trigger date, affected area count, reviewer name, review notes, and a link to the admin detail page.
3. Sends to each matched recipient and writes a `NotificationLog` row (unique per event + recipient email).
4. Updates `ArcTriggerEvent.status` → `SENT` or `SEND_FAILED`.

**`NotificationRecipient`** — email distribution list entry.

| Field | Notes |
|---|---|
| `email` / `name` / `organization` | Contact details |
| `admin_area_ids` | `ArrayField(IntegerField)` — which districts this person covers |
| `is_active` | Inactive recipients are excluded from all sends |

**`NotificationLog`** — immutable audit trail, one row per (event, recipient email) pair.

| Field | Notes |
|---|---|
| `trigger_event` | FK → `ArcTriggerEvent` |
| `recipient` | FK → `NotificationRecipient` (nullable; `SET_NULL` on delete) |
| `recipient_email` | Snapshot of the email address at send time |
| `status` | `sent` / `failed` / `bounced` |
| `provider_message_id` | ID returned by the email provider |
| `error` | Error detail if delivery failed |

---

## HDX reference datasets

Manually loaded from [HDX](https://data.humdata.org/) via the Django admin panel. Small structured datasets are stored inline in a `data` JSONB column; larger files are stored in Azure Blob and referenced by `file_blob_url`. These are read-only reference data and do not participate in the trigger workflow.
