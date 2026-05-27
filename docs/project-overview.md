# Malawi Risk Watch — Project Overview

**Audience:** QA engineers, project managers, new team members.
This document explains what the system does, who it serves, and how data moves through it — without assuming prior technical knowledge of the codebase.

---

## What is this system?

Malawi Risk Watch is a **disaster risk management platform** built for the **Malawi Red Cross Society (MRCS)**. Its purpose is to detect flood and drought risk conditions early and alert the right people before a disaster unfolds.

The system ingests two independent streams of hazard data every day:

1. **JBA flood forecasts** — probabilistic flood depth maps for Malawi over the next 10 days.
2. **ARC parametric rainfall observations** — daily rainfall measurements per administrative district, checked against pre-agreed thresholds.

When thresholds are exceeded, the system creates an alert for MRCS staff to review. If staff confirm the alert, emails are automatically sent to a configured list of recipients. If staff reject it, nothing goes out.

In addition, the system stores **HDX reference datasets** (administrative boundary files, population data, etc.) which are used to contextualise the hazard data.

All processed data is also intended to feed into the **IFRC Go platform** — the global IFRC situational awareness tool — though that integration is planned for a future phase.

---

## Who uses it?

| Role | What they do in the system |
|---|---|
| **MRCS Staff (Reviewers)** | Log into the admin panel to review ARC trigger events, confirm or reject alerts, and view notification history |
| **MRCS Staff (Admins)** | Manage the email distribution list; load HDX datasets |
| **IFRC / Partner organisations** | Receive email alerts when a trigger event is confirmed |
| **Data consumers (future)** | Query processed data via GraphQL API (e.g. IFRC Go integration) |

---

## Where does data come from?

| Source | Type | Frequency | Delivery method |
|---|---|---|---|
| **JBA** | Flood forecast GeoTIFFs + CSV | Daily | Automated ingestion job |
| **ARC** | Rainfall observation CSV | Daily | Automated daily ingestion job |
| **HDX** | Reference datasets (GeoJSON/CSV) | Manual | MRCS admin uploads via admin panel |

---

## High-level system architecture

```
External sources
    │
    ├─ JBA API ──────────────────► Ingestion job (daily Celery task)
    │                                     │
    │                              ┌──────▼───────┐
    │                              │  PostgreSQL   │
    └─ ARC API ──► Ingestion job ──►│  (PostGIS)   │◄── MRCS Admin (HDX load)
                                   └──────┬───────┘
                                          │
                         ┌────────────────┼─────────────────┐
                         │                │                  │
                    JBA viewer       ARC trigger        GraphQL API
                 (flood maps on     workflow           (future IFRC Go
                  frontend map)    (review → email)    integration)
```

Files (TIFFs, CSVs, HDX uploads) are stored in **storage**. The database holds metadata and processed statistics — not raw raster pixels.

---

## How data is presented to end users

### Frontend map (flood and rainfall data)
The frontend displays JBA flood forecast maps as **Cloud-Optimized GeoTIFFs (COGs)** served directly from storage. The map allows users to:
- Browse forecasts by lead day (1–10 days ahead)
- See which administrative districts are most affected
- Inspect ensemble statistics per district (mean, median, 75th/90th percentile flood depth)

ARC rainfall events are displayed as **clickable points on the map** — one point per event. Clicking a point opens a detail panel showing the trigger date, affected districts, rainfall values, and the current workflow status.

### IFRC Go risk page integration
From the IFRC Go risk page, MRCS staff can act on a confirmed ARC trigger event directly within the Go platform:
- **Assign to an existing Go emergency or event** — links the trigger to an ongoing response operation already tracked in Go.
- **Create a field report** — opens a new field report in Go, pre-populated with the event details, for staff to complete and submit.

### Admin panel (operations)
MRCS staff use a Django admin panel to:
- Review and act on ARC trigger events (confirm / reject)
- Manage the email distribution list
- Load HDX reference datasets
- View notification history

### GraphQL API
A GraphQL endpoint exposes all processed data for consumption by external tools. The frontend and IFRC Go integration both use this API.

---

## Data flow 1 — JBA Flood Forecast

JBA is a commercial flood forecast data provider. Every day they produce a probabilistic flood forecast for Malawi.

### What JBA delivers per daily run
- **10 GeoTIFF files** — one per forecast lead time (lead day 1 through 10). Each TIFF is a raster map of flood depth across Malawi, encoding 51 ensemble members as separate bands.
- **1 CSV file** — ensemble statistics aggregated per district (mean, median, 75th percentile, 90th percentile, max flood depth, and count of non-zero ensemble members).

### Ingestion flow

```
JBA API
  │
  ▼
Ingestion job starts → creates JbaIngestionRun record (status: running)
  │
  ├─ Downloads 10 TIFFs
  │     │
  │     └─ Converts each TIFF to Cloud-Optimized GeoTIFF (COG)
  │           └─ Saves to Azure Blob (path: jba/tiff/{date}/lead{N}.tif)
  │                 └─ Creates FloodForecastFile record
  │
  ├─ Downloads 1 CSV
  │     └─ Saves to Azure Blob (path: jba/csv/{date}/...)
  │           └─ Saves CSV path on JbaIngestionRun
  │
  ├─ Parses CSV → creates FloodForecastImpact rows
  │     (one row per district per lead day — ~320 rows per run)
  │
  └─ Marks JbaIngestionRun status: success (or failed/partial)
```

### Key data model relationships

```
JbaIngestionRun  (one per day)
  │  run_date, status, csv (aggregate CSV file)
  │
  └─► FloodForecastFile  (10 per run — one per lead day)
        │  forecast_issue_date, forecast_target_date, tiff (COG file)
        │
        └─► FloodForecastImpact  (one per district per lead day)
              band_5_mean, band_5_median, band_5_p75, band_5_p90, band_5_max
              ensembles_nonzero_count
```

### What "lead time" means
Lead time is always computed as `forecast_target_date − forecast_issue_date`. It is not stored as a column — if you need lead day 3, filter for records where `target − issue = 3 days`.

### COG conversion
Each TIFF from JBA is converted to a **Cloud-Optimized GeoTIFF** before storage. This format is internally tiled and includes overview zoom levels, allowing the frontend map to stream only the pixels needed for the current viewport — without downloading the entire file. This happens automatically during ingestion and is transparent to end users.

### Status values for ingestion runs

| Status | Meaning |
|---|---|
| `pending` | Job queued, not yet started |
| `running` | Actively downloading and processing |
| `success` | All expected files downloaded and parsed |
| `partial` | Some files processed; others failed |
| `failed` | Run failed entirely |

---

## Data flow 2 — ARC Parametric Rainfall

ARC (Africa Rainfall Climatology) provides daily rainfall measurements per administrative district. Unlike JBA's probabilistic flood forecasts, ARC data is used for **parametric triggers** — pre-agreed rules that automatically create an alert if rainfall exceeds a threshold.

### What ARC delivers
A daily CSV with one row per district containing:
- `rainfall_raw` — raw rainfall measurement
- `rainfall` — processed/adjusted value
- `impact` — derived impact score
- `event_rp` — return period in years (how rare this event is)
- `cell_trigger` — boolean flag set by JBA's algorithm indicating the threshold was crossed

### Ingestion flow

```
ARC API
  │
  ▼
Daily ingestion job (Celery task)
  │
  ├─ Downloads ARC CSV
  │     └─ Saves to Azure Blob
  │
  ├─ Parses CSV → creates ArcRainfallObservation rows
  │     (one row per district — ~32 rows per day)
  │
  └─ Threshold check: were any cell_trigger = true?
        │
        ├─ No triggers → nothing happens
        │
        └─ Yes triggers → creates ArcTriggerEvent
              (status: pending_review)
              Lists all affected district IDs
```

### Key data model relationships

```
ArcRainfallObservation  (one per district per day)
  observation_date, admin_area, rainfall_raw, rainfall,
  impact, event_rp, cell_trigger

ArcTriggerEvent  (created when threshold crossed — one per trigger date)
  trigger_date, triggered_admin_areas_count, affected_admin_areas,
  status, reviewed_by, reviewed_at, review_notes, email_sent_at
```

---

## ARC Trigger Event — Approval / Rejection Workflow

When the daily ARC ingestion detects that one or more districts exceeded the rainfall threshold, a **trigger event** is created and enters a review workflow. No alert emails are sent until a human approves.

### Full workflow lifecycle

```
ARC threshold crossed
        │
        ▼
  ArcTriggerEvent created
  status: pending_review
        │
        ▼
  MRCS staff notified (internal — e.g. system notification or direct admin panel visit)
        │
        ▼
  Staff opens admin panel → reviews trigger event
  Can see: trigger date, which districts triggered, rainfall values
        │
        ├──── Reject ──────────────────────────────────────────────────────────┐
        │      Sets status: rejected                                           │
        │      Records: reviewed_by (user), reviewed_at, review_notes          │
        │      Result: no emails sent, event closed                            │
        │                                                                      │
        └──── Confirm ─────────────────────────────────────────────────────────┤
               Sets status: confirmed                                          │
               Records: reviewed_by (user), reviewed_at, review_notes         │
               │                                                               │
               ▼                                                               │
         Email job triggered (Celery)                                          │
               │                                                               │
               ├─ Looks up active NotificationRecipients                       │
               │   scoped to affected districts                                │
               │                                                               │
               ├─ Sends alert email to each recipient                          │
               │                                                               │
               ├─ Creates NotificationLog per recipient                        │
               │   (status: sent / failed / bounced)                           │
               │                                                               │
               └─ Updates ArcTriggerEvent                                      │
                   status: sent (all succeeded)                                │
                   or: send_failed (one or more failed)                        │
                   email_sent_at: timestamp                                    │
                                                                               │
◄──────────────────────────────────────────────────────────────────────────────┘
```

### Status values explained

| Status | Who sets it | Meaning |
|---|---|---|
| `pending_review` | System (automatic) | Trigger created, awaiting staff action |
| `confirmed` | MRCS staff | Threshold crossed is judged a real event; emails will be sent |
| `rejected` | MRCS staff | False alarm or not actionable; no emails sent |
| `sent` | System (automatic) | All alert emails delivered successfully |
| `send_failed` | System (automatic) | One or more emails failed; check notification log |

### Review notes
Staff can attach free-text notes when confirming or rejecting. This creates an audit trail explaining the decision — important for accountability and post-event review.

### Notification recipients
Recipients are maintained in a distribution list by MRCS admins. Each recipient can be **scoped to specific districts** — they only receive alerts for districts they are responsible for. If a trigger event only affects districts in the south, only recipients scoped to those districts receive an email.

### Audit trail
Every email send attempt is recorded in `NotificationLog`. The recipient's email address is **snapshotted at send time** so the log is preserved even if the recipient is later removed from the distribution list.

---

## Data flow 3 — HDX Reference Datasets

HDX (Humanitarian Data Exchange) is the UN OCHA open data platform. Reference datasets such as Malawi administrative boundary shapefiles, population data, and vulnerability indices are sourced from HDX and loaded manually.

### What HDX data is used for
- Administrative boundary polygons (district shapes displayed on the map)
- Population and vulnerability reference data for contextualising flood impacts

### Load flow

```
MRCS admin downloads dataset from HDX
        │
        ▼
  Uploads via Django admin panel
        │
        ├─ Small datasets: stored inline as JSON in the database
        │
        └─ Large files: uploaded to storage
              Metadata (name, source URL, file type, who loaded it)
              recorded in HdxDataset table
```

### Dataset types supported
- `GeoJSON` — boundary and vector data
- `CSV` — tabular reference data

HDX datasets are not updated automatically — they are refreshed manually when the underlying reference data changes (e.g. after a census update or boundary revision).

---

## Future integrations

| Integration | Status | Notes |
|---|---|---|
| **IFRC Go — data feed** | Planned | Processed flood and rainfall data will be pushed to the IFRC Go situational awareness platform via its API |
| **IFRC Go — risk page** | Planned | MRCS staff will be able to assign a confirmed trigger event to an existing Go emergency or create a field report directly from the Go risk page |
| **IFRC Go JWT auth** | Planned | User authentication will mirror IFRC Go accounts; currently uses local Django auth |

---

## Glossary

| Term | Definition |
|---|---|
| **JBA** | JBA Risk Management — commercial flood forecast data provider |
| **ARC** | Africa Rainfall Climatology — satellite-derived daily rainfall dataset |
| **HDX** | Humanitarian Data Exchange — UN OCHA open data platform |
| **MRCS** | Malawi Red Cross Society |
| **IFRC Go** | IFRC's global disaster operations platform |
| **COG** | Cloud-Optimized GeoTIFF — a raster file format optimised for streaming over HTTP |
| **Lead time** | Number of days between forecast issue date and the date being forecast |
| **Parametric trigger** | An automatic threshold rule: if rainfall exceeds X, create an alert — no human judgement required to detect it, only to act on it |
| **Return period** | How rare a rainfall event is statistically, expressed in years (e.g. a 1-in-10-year event has `event_rp = 10`) |
| **Ensemble** | JBA delivers 51 model runs (ensemble members) per forecast; statistics like mean and 90th percentile are calculated across all 51 members |
| **Admin area** | A Malawi administrative district — the spatial unit used throughout the system |
