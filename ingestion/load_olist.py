from google.cloud import bigquery, storage
import datetime
from pathlib import Path
from dotenv import load_dotenv
import csv
import os

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
        header = next(reader)
        local_row_count = sum(1 for row in reader)  # count non-empty rows

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
        load_job.result()
    except Exception:
            print(load_job.errors)
            raise
    try:
        # 2. Validate row count
        validate_row_count(table, count_csv_rows, load_job.output_rows)
        
        # 3. temp table -> final table (atomic replace)
        bq_client.query(query, job_config=query_config).result()

        rows = load_job.output_rows
        print(f"Loaded {rows} rows to {table_id}")
        return rows, table_id
    
    finally:
        # 3. clean up temp table
        bq_client.delete_table(tmp_id, not_found_ok=True)
        print(f"Deleted temp table {tmp_id}")

def main():
    config = load_config()
    load_date = datetime.date.today().isoformat()
    storage_client = storage.Client(project=config["project_id"])
    bucket = storage_client.bucket(config["bucket_name"])
    bq_client = bigquery.Client(project=config["project_id"])
    gcs_uris = {}
    bq_rows = {}

    for table,file_name in FILES.items():
        file_path = Path(config["data_dir"]) / file_name
        gcs_uri = upload_to_gcs(table, file_path, bucket, load_date)
        rows, table_id = load_to_bigquery(bq_client, config["bigquery_dataset"], table, gcs_uri, file_path)

        bq_rows[table_id] = rows
    
    print(bq_rows)
if __name__ == "__main__":
    main()