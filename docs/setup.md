# Google Cloud CLI
  gcloud init
  gcloud auth application-default login
  gcloud services enable bigquery.googleapis.com storage.googleapis.com

  gcloud storage buckets create gs://olist-analytics-eduardo-landing `
    --project=olist-analytics-eduardo `
    --location=europe-west2 `
    --uniform-bucket-level-access `
    --public-access-prevention

  bq mk --dataset `
    --location=europe-west2 `
    --description="Raw landing tables loaded from GCS. No transformations." `
    olist-analytics-eduardo:raw

# GitHub
  git clone https://github.com/ecristaldo/olist-analytics-platform.git

  cd olist-analytics-platform
  mkdir data

# Dataset
  Download Olist Brazilian e-commerce dataset from Kaggle [LINK](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  Extract its contents into `data` folder

# Python
  Create VENV: `python -m venv .venv`
  Activate: `.venv\Scripts\Activate.ps1`
  Install packages: `pip install -r requirements.txt`
  Ingestion:
    Olist: python .\ingestion\load_olist.py
    ECB FX: python .\ingestion\load_fx.py

# Environment Variables
  `copy .env.example .env` and fill in the values

# dbt
  `cd olist_dbt`
  `dbt deps`
  `dbt build`

  Make sure `~/.dbt/profiles.yml` has `location: europe-west2`