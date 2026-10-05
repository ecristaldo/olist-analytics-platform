## Design decisions

- **Location: europe-west2 (London)** for all resources — UK data residency (UK GDPR).
  A BigQuery load job needs the GCS bucket in the same location as the dataset.
- **FX rates in `raw.fx_rates`** (same dataset as Olist) because for this project I can keep in the same dataset.

- **Ingestion in BQ failed**
  For small datasets, reloading everything is ok. But with massive datasets this would pose a problem.
  The script will skip the dataset that failed (will be saved in log file) and will keep going.
  When done, I will fix the issue and two options:
    a. can manually run the failed dataset
    b. the script will try again all failed datasets reading from the log file.

  **The trade-off to write down**
  Ther loader protects each table individually. The atomic replace means a failed table keeps yesterday's version. But across tables, you might end up with olist_order_items from today and olist_orders from yesterday, which are out of step with each other.


  # ##TODO
  **The retry mechanism (--tables and --retry-failed)**
  **Catch KeyboardInterrupt to log interrupted before stoping. (For CTRL+C)**
  **record the BigQuery job_id in the log. Then a dead run can be matched to INFORMATION_SCHEMA.JOBS with a simple join, with no detective work.**