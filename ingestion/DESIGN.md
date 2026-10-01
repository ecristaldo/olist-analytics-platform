1- The path would be GCS: 'gs://olist-analytics-eduardo-landing/olist/orders/load_date=2026-09-25/olist_orders_dataset.csv'
FX: 'gs://olist-analytics-eduardo-landing/fx/rates/load_date=2026-09-25/fx_rates.json'

2- Olist would be fixed snapshot because the CSVs never get new entries, so would a full replace (WRITE_TRUNCATE) for each load, the table would be replaced completly every time.
FX would be incremental because rates changes every day and would only load dates I don't have yet.
In case FX load crashes after load half the dates,There will be 2 layers:
  1. One load job per run, which is atomic and prevents half-written data
  2. MERGE on rate_date when inserting into raw.fx_rates, as a safety net. If the same date arrives twice, it's updated instead of duplicated.

3- Load all raw columns as STRING to make sure nothing is lost (ie.: 0312 -> 312 when converted to INT), and later the field type can be sorted out on dbt's staging layer.

4- I going to have on both column and path. Column to keep dbt's freshness and the path to know from which file every row came.
For the hard part when CSV load pattern with a temporary table is safe is because the _loaded_at field witch is a TIMESTAMP, with that we can narrow down not only by date but by miliseconds. Making easier to find where to start loading again in case of a crash. I would apply the same solution from point 2 with FX data.
I would also add those 2 columns:
_loaded_at (TIMESTAMP): when it was loaded
_source_uri (STRING): the full GCS path it came from

5- Would have run_id,source (Olist, FX),status (started, sucess, failed), error_msg, started_at, finished_at,path,num_rows, error_msg.
I woudl write the log at the same time is loading as append-only and not UPDATE a row, if failed I would know why and where.
In case the process diw half-way the log would show a something like that:
run_id,source (Olist, FX),status (started, sucess, failed), started_at, finished_at,num_rows,file_name,path,error_msg
alb1, "Olist", "Started", 2026-09-35T23:52:34Z,NUll,Null, 'gs://olist-analytics-eduardo-landing/olist/orders/load_date=2026-09-25/olist_orders_dataset.csv',Null
alb1, "Olist", "Success", 2026-09-35T23:52:34Z, 2026-09-35T23:52:34Z, 9473, 'gs://olist-analytics-eduardo-landing/olist/orders/load_date=2026-09-25/olist_orders_dataset.csv',Null
cre3, "Olist", "Started", 2026-09-35T23:52:34Z,Null, Null, 'gs://olist-analytics-eduardo-landing/olist/orders/load_date=2026-09-25/olist_orders_dataset.csv',Null