#Google Cloud CLI
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

#GitHub
git clone https://github.com/ecristaldo/olist-analytics-platform.git

cd olist-analytics-platform
mkdir ingestion
mkdir data
