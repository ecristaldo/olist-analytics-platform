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
Cause: Row had a String field with line break causing to read as and new row.
Fix: allow_quoted_newlines=True, plus a row-count comparison against the local file
Trade-off: slower loads for large files, because BigQuery can't parallelise as much
What I didn't do: max_bad_records, because it would drop reviews silently

## #3 - Local vs BQ row count
Date: 30/09/2026
What happened: the row check counted columns instead of rows
Fix: saved the reader in a variable, took the header with next() 
Trade-off: slower loads for large files, because BigQuery can't parallelise as much
What I didn't do: max_bad_records, because it would drop reviews silently

## #4 - Loaded empty file successfuly
Date: 01/10/2026
What happened: empty file loaded and erased a table.
Fix: refuse files with 0 rows 

## #5 - Force Stop script (CTRL+C)
Date: 01/10/2026
What happened: Python died, BigQuery finished the job. The log says geolocation never completed, but the table was replaced at 17:44:10, 9 seconds after started_at. The cleanup also ran: finally executed even with the Ctrl+C.

## #6
Date: 04/10/2026
What happened: ReadTimeout from ECB API
Cause: ECB took more than 30s to answer the probe and th retry handled on its own.

## #7 Rates with gaps on downtime
Date: 04/10/2026
What happened: today − 7 would leave gaps after downtime
Fix: changed to a high-water mark, going to query BQ for latest date loaded and will set START_DATE = MAX(TIME_PERIOD) - 7 when calling the API

## #8
Date: 05/10/2026
What happened: dbt could not locate the dataset.
Cause: the `location` in profiles.yml was configured for 'EU' and not the correct `europe-west2`
Fix: replace for Eu for europe-west2

## #9
Date: 06/10/2026
What happened: Timestamps with mixed meanings caught by a test.
Cause: The date filds in olist_orders are timestamps from Sao Paulo Brazil, 3 where set as Europe UTC.
Fix: changed all to timestamps for Sao Paulo on stg_olist_orders.sql

## #10
**Date**: 07/10/2026
**What happened**: ENV drifted from Requirements.txt between 2 machines
**Cause**: I moved from my laptop to my desktop mid-project. The desktop environment drifted from requirements.txt, which still pinned a storage client version that dbt-bigquery doesn't accept. Both machines ran fine, but the file described an environment that existed nowhere. The first CI run installed strictly from the file and the resolver failed. 
**Fix**: pinned a compatible version, verified with pip check and a loader run, and split ingestion and dbt dependencies. Lesson: environments get built from the requirements file, never the other way round, and CI is what enforces that.