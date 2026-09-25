## Design decisions

- **Location: europe-west2 (London)** for all resources — UK data residency (UK GDPR).
  A BigQuery load job needs the GCS bucket in the same location as the dataset.
- **FX rates in `raw.fx_rates`** (same dataset as Olist) because for this project I can keep in the same dataset.