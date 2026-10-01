## #0 — Gcloud init
Date: 25/09/2026
What happened: gcloud init failed to set a Compute Engine zone
Cause: Because the API was disabled
Fix / decision: Not needed for this project, so ignored

## #1 — File Ingestion
Date: 25/09/2026
What happened: The hard-coded file list that didn't match the real dataset
Cause: File name was wrong, 1 didn't exist and was missing 1 file.
Fix / decision: Created a file check in the script that will stop if a file is missing.

## #2 - BiqQuery ingestion error
Date: 30/09/2026
What happened: order_reviews load failed at row 774
Fix: allow_quoted_newlines=True, plus a row-count comparison against the local file
Trade-off: slower loads for large files, because BigQuery can't parallelise as much
What I didn't do: max_bad_records, because it would drop reviews silently

