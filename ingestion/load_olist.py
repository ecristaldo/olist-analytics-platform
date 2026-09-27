from google.cloud import storage
import datetime
from pathlib import Path
from dotenv import load_dotenv
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
    REQUIRED_ENV_VARS = ["PROJECT_ID", "BUCKET_NAME", "DATA_DIR"]

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
    }

def upload_to_gcs(table, file_path, bucket, load_date):
    file_name = Path(file_path).name
    path = f"olist/{table}/load_date={load_date}/{file_name}"
    gcs_uri = f"gs://{bucket.name}/{path}"
    blob = bucket.blob(path)
    blob.upload_from_filename(file_path)
    
    print(f"File {file_path} uploaded to {path}")

    return gcs_uri

def main():
    config = load_config()
    load_date = datetime.date.today().isoformat()
    storage_client = storage.Client(project=config["project_id"])
    bucket = storage_client.bucket(config["bucket_name"])
    gcs_uris = {}

    for table,file_name in FILES.items():
        file_path = Path(config["data_dir"]) / file_name
        gcs_uri = upload_to_gcs(table, file_path, bucket, load_date)
        gcs_uris[table] = gcs_uri
    
    print(gcs_uris)

if __name__ == "__main__":
    main()