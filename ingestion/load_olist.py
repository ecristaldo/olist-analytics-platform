from google.cloud import bigquery, storage
import datetime
from pathlib import Path
from dotenv import load_dotenv
import csv
import uuid
import os
import sys

FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
}

SOURCE = "olist"

def load_config():
    load_dotenv()  # loads .env from current directory (or any parent)
    REQUIRED_ENV_VARS = ["PROJECT_ID", "BUCKET_NAME", "DATA_DIR", "BIGQUERY_DATASET"]

    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    missing_files = [file for file in FILES.values() if not (Path(os.getenv("DATA_DIR")) / file).exists()]
    if missing_files:
        raise FileNotFoundError(
            f"Missing required files: {', '.join(missing_files)}"
        )

    return {
        "project_id": os.getenv("PROJECT_ID"),
        "bucket_name": os.getenv("BUCKET_NAME"),
        "data_dir": os.getenv("DATA_DIR"),
        "bigquery_dataset": os.getenv("BIGQUERY_DATASET"),
    }

def upload_to_gcs(table, file_path, bucket, load_date):
    file_name = Path(file_path).name
    path = f"olist/{table}/load_date={load_date}/{file_name}"
    gcs_uri = f"gs://{bucket.name}/{path}"
    blob = bucket.blob(path)
    blob.upload_from_filename(file_path)

    return gcs_uri

def validate_row_count(table, local_rows, bq_rows):
    if local_rows == 0:
        raise ValueError(f"{table}: source file has no data rows, refusing to replace table")
    if local_rows != bq_rows:
        raise ValueError(
            f"Row count mismatch for {table}: local file has {local_rows}, BigQuery loaded {bq_rows}"
        )
    print(f"{table}: row count OK ({bq_rows})")

def load_to_bigquery(bq_client, dataset, table, gcs_uri, local_file_path):
    table_id = f"{bq_client.project}.{dataset}.olist_{table}"
    tmp_id = f"{bq_client.project}.{dataset}._tmp_olist_{table}"

    with open(local_file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"{table}: source file has no header row")
        local_row_count = sum(1 for row in reader)

    schema = [bigquery.SchemaField(col, "STRING") for col in header]

    load_job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
        encoding="UTF-8",
    )
    
    query = f"""
        CREATE OR REPLACE TABLE `{table_id}` AS
        SELECT
            *,
            CURRENT_TIMESTAMP() AS _loaded_at,
            @source_uri AS _source_uri
        FROM `{tmp_id}`
    """
    query_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("source_uri", "STRING", gcs_uri),
        ]
    )

    try:
        # 1. GCS -> temp table
        load_job = bq_client.load_table_from_uri(gcs_uri, tmp_id, job_config=load_job_config)
        try:
            load_job.result()
        except Exception as e:
            raise RuntimeError(f"Load failed: {e} | job errors: {load_job.errors}") from e

        # 2. Validate row count
        validate_row_count(table, local_row_count, load_job.output_rows)
        
        # 3. temp table -> final table (atomic replace)
        bq_client.query(query, job_config=query_config).result()

        print(f"Loaded {load_job.output_rows} rows to {table_id}")
        return load_job.output_rows, table_id, local_row_count
    
    finally:
        # 4. clean up temp table
        bq_client.delete_table(tmp_id, not_found_ok=True)
        # print(f"Deleted temp table {tmp_id}")

def ensure_log_table(bq_client, dataset):
    table_id = f"{bq_client.project}.{dataset}._log_ingestion"

    schema = [
        bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED"), # started, success, failed
        bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("event_at", "TIMESTAMP", mode="REQUIRED"), # It's when this row was written
        bigquery.SchemaField("duration_seconds", "FLOAT64"),
        bigquery.SchemaField("source_row_count", "INT64"),
        bigquery.SchemaField("loaded_row_count", "INT64"),
        bigquery.SchemaField("gcs_uri", "STRING"),
        bigquery.SchemaField("error_message", "STRING"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(field="event_at")
    bq_client.create_table(table, exists_ok=True)
    return table_id

def log_event(bq_client, log_table_id, run_id, table, status, started_at, *,
              source, gcs_uri=None, source_rows=None, loaded_rows=None, error=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    row = {
        "run_id": run_id,
        "source": source,
        "table_name": table,
        "status": status,
        "started_at": started_at.isoformat(),
        "event_at": now.isoformat(),
        "duration_seconds": None if status == "started" else (now - started_at).total_seconds(),
        "source_row_count": source_rows,
        "loaded_row_count": loaded_rows,
        "gcs_uri": gcs_uri,
        "error_message": error[:2000] if error else None,
    }
    try:
        errors = bq_client.insert_rows_json(log_table_id, [row])
        if errors:
            print(f"WARNING: failed to write log row: {errors}")
    except Exception as e:
        print(f"WARNING: failed to write log row: {e}")

def main():
    config = load_config()
    load_date = datetime.date.today().isoformat()
    storage_client = storage.Client(project=config["project_id"])
    bucket = storage_client.bucket(config["bucket_name"])
    bq_client = bigquery.Client(project=config["project_id"])
    dataset = config["bigquery_dataset"]
    

    log_table_id = ensure_log_table(bq_client, dataset)
    run_id = uuid.uuid4().hex
    bq_rows = {}
    succeeded = []
    failures = []

    for table,file_name in FILES.items():
        file_path = Path(config["data_dir"]) / file_name
        started_at = datetime.datetime.now(datetime.timezone.utc)
        gcs_uri = None
        log_event(bq_client, log_table_id, run_id, table, "started", started_at, source=SOURCE)
        
        try:
            gcs_uri = upload_to_gcs(table, file_path, bucket, load_date)
            rows, table_id, source_rows = load_to_bigquery(bq_client, dataset, table, gcs_uri, file_path)
            bq_rows[table_id] = rows
            succeeded.append(table)
            log_event(bq_client, log_table_id, run_id, table, "success", started_at,
                    source=SOURCE, gcs_uri=gcs_uri, source_rows=source_rows, loaded_rows=rows)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            print(f"FAILED {table}: {error}")
            log_event(bq_client, log_table_id, run_id, table, "failed", started_at, source=SOURCE, gcs_uri=gcs_uri, error=error)
            failures.append(table)
    
    summary = f"{len(succeeded)} succeeded, {len(failures)} failed"
    if failures:
        print(f"{summary}: {', '.join(failures)}")
        sys.exit(1)
    print(summary)

if __name__ == "__main__":
    main()