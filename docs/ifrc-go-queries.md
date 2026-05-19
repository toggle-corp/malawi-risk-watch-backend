# IFRC Go — GraphQL Query Reference

Queries the IFRC Go platform (or any consumer) should use to power the Malawi Risk Watch map layers and event displays.

**GraphQL endpoint:** `http://localhost:8060/graphql` (dev) / `https://<prod-domain>/graphql` (prod)

All queries use offset-based pagination (`offset` / `limit`). The `filters` argument is optional on every list query — omit it to fetch all records.

---

## HDX map layers

HDX datasets are stored as CSV files. Fetch by `dataset_name` to retrieve the `file_blob_url` pointing to the CSV in storage.

### List all available datasets

```graphql
query HdxDatasets {
  hdxDatasets {
    totalCount
    results {
      id
      datasetName
      description
      fileType
      fileBlobUrl
      loadedAt
    }
  }
}
```

### Fetch a specific dataset by name

Use the `search` filter (matches `dataset_name` or `description`):

```graphql
query HdxDataset($name: String!) {
  hdxDatasets(filters: { search: $name }) {
    results {
      id
      datasetName
      fileBlobUrl
      loadedAt
    }
  }
}
```

**Variables:**
```json
{ "name": "MWI_ADM2_flood_exposure" }
```

### Available dataset names

| `dataset_name` | Content |
|---|---|
| `MWI_ADM2_flood_exposure` | Flood exposure per district at RP 10/50/100/500 years (30cm depth) — use for the risk map layer |
| `MWI_ADM2_vulnerability` | Vulnerable population counts per district |
| `MWI_ADM2_demographics` | Total population demographics per district |
| `MWI_ADM2_access` | Population accessibility to hospitals and education per district |
| `MWI_ADM2_facilities` | Hospital counts per district |
| `MWI_ADM2_rural_population` | Rural population breakdown per district |

---

### ARC rainfall observations for a specific date

Useful for rendering per-district rainfall intensity on the map:

```graphql
query ArcObservations($date: Date!) {
  arcRainfallObservations(
    filters: { observationDate: { exact: $date } }
    order: { observationDate: DESC }
  ) {
    totalCount
    results {
      id
      observationDate
      adminAreaId
      adminArea {
        id
        name
        pcode
        level
        centroid
      }
      rainfall
      rainfallRaw
      impact
      eventRp
      cellTrigger
    }
  }
}
```

**Variables:**
```json
{ "date": "2026-05-12" }
```

---

## JBA flood forecast

### Latest forecast impacts (for flood risk map layer)

Fetch the most recent `forecast_issue_date` and a specific lead time:

```graphql
query FloodForecastImpacts($issueDate: Date!, $targetDate: Date!) {
  floodForecastImpacts(
    filters: {
      forecastIssueDate: { exact: $issueDate }
      forecastTargetDate: { exact: $targetDate }
    }
    order: { forecastIssueDate: DESC }
  ) {
    totalCount
    results {
      id
      forecastIssueDate
      forecastTargetDate
      leadTimeDays
      adminAreaId
      adminArea {
        id
        name
        pcode
        level
        centroid
      }
      band5Mean
      band5Median
      band5P75
      band5P90
      band5Max
      ensemblesNonzeroCount
    }
  }
}
```

**Variables:**
```json
{
  "issueDate": "2026-05-18",
  "targetDate": "2026-05-21"
}
```

> `leadTimeDays` is a computed field (`targetDate - issueDate`). Use `band5P90` or `band5Max` as the primary risk indicator for map colouring; `ensemblesNonzeroCount` (out of 51) gives a confidence signal.

### List available ingestion runs (to discover available dates)

```graphql
query JbaIngestionRuns {
  jbaIngestionRuns(
    filters: { status: "success" }
    order: { runDate: DESC }
    pagination: { offset: 0, limit: 10 }
  ) {
    totalCount
    results {
      id
      runDate
      forecastIssueTime
      filesProcessed
      csvBlobUrl
    }
  }
}
```

### TIFF files for a run (to get blob URLs per lead time)

```graphql
query FloodForecastFiles($runId: ID!) {
  floodForecastFiles(
    filters: { ingestionRunId: $runId }
    order: { forecastTargetDate: ASC }
  ) {
    results {
      id
      forecastIssueDate
      forecastTargetDate
      leadTimeDays
      tiffBlobUrl
      fileSizeBytes
    }
  }
}
```

---

## Admin areas (for map boundary layer)

```graphql
query AdminAreas($level: Int!) {
  adminAreas(filters: { level: { exact: $level } }) {
    results {
      id
      name
      pcode
      level
      centroid
      bbox
      parent {
        id
        name
      }
    }
  }
}
```

**Variables:**
```json
{ "level": 2 }
```

> Level 2 = districts (32 total). Use `pcode` to join against the HDX CSV datasets (column `ADM2_PCODE`). Use `centroid` / `bbox` for initial map positioning.

---

## Suggested data flow for the IFRC Go map

```
1. Load district boundaries
   adminAreas(level: 2) → render base district polygons

2. Colour by flood risk
   floodForecastImpacts(issueDate, targetDate) → join on adminAreaId
   → colour by band5P90

3. Overlay ARC trigger events
   arcTriggerEvents(status: "sent") → highlight affectedAdminAreas

4. Show vulnerability / exposure context
   hdxDatasets(search: "MWI_ADM2_flood_exposure") → download CSV from fileBlobUrl
   → join on ADM2_PCODE ↔ adminArea.pcode
```
