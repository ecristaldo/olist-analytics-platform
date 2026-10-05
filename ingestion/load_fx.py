import csv
import datetime
import io
import os
import random
import sys
import time
import uuid

import requests
from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.cloud import bigquery, storage

from load_olist import ensure_log_table, log_event

URL_TEMPLATE = "https://data-api.ecb.europa.eu/service/data/EXR/D.{key}.EUR.SP00.A"
MAX_ATTEMPTS = 5
TIMEOUT = 30
MAX_DELAY = 60

SOURCE = "ecb_fx"
TABLE = "rates"                    # GCS: fx/rates/...   BigQuery: ecb_fx_rates
MERGE_KEYS = ("KEY", "TIME_PERIOD")
LOOKBACK_DAYS = 7                  # normal run: MAX(TIME_PERIOD) in the table - 7 days (MERGE makes the overlap safe)
DEFAULT_START_DATE = "2016-01-01"  # USE_DEFAULT_START_DATE=True, or nothing loaded yet to anchor on


def load_config():
    load_dotenv()  # loads .env from current directory (or any parent)
    REQUIRED_ENV_VARS = ["PROJECT_ID", "BUCKET_NAME", "BIGQUERY_DATASET", "FX_CURRENCIES"]

    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    currencies = [c.strip().upper() for c in os.getenv("FX_CURRENCIES").split(",") if c.strip()]
    if not currencies:
        raise EnvironmentError("FX_CURRENCIES is set but contains no currency codes")

    use_default = (os.getenv("USE_DEFAULT_START_DATE") or "false").strip().lower()
    if use_default not in ("true", "false"):
        raise EnvironmentError(
            f"USE_DEFAULT_START_DATE must be True or False, got {os.getenv('USE_DEFAULT_START_DATE')!r}"
        )

    return {
        "project_id": os.getenv("PROJECT_ID"),
        "bucket_name": os.getenv("BUCKET_NAME"),
        "bigquery_dataset": os.getenv("BIGQUERY_DATASET"),
        "fx_currencies": currencies,
        "use_default_start_date": use_default == "true",
    }


def validate_row_count(table, local_rows, bq_rows):
    if local_rows == 0:
        raise ValueError(f"{table}: source file has no data rows, refusing to replace table")
    if local_rows != bq_rows:
        raise ValueError(
            f"Row count mismatch for {table}: local file has {local_rows}, BigQuery loaded {bq_rows}"
        )
    print(f"{table}: row count OK ({bq_rows})")


def table_ids(bq_client, dataset, table):
    final_id = f"{bq_client.project}.{dataset}.ecb_fx_{table}"
    tmp_id = f"{bq_client.project}.{dataset}._tmp_ecb_fx_{table}"
    return final_id, tmp_id


def parse_ecb_csv(text):
    """Return (header, row_count). Checks the merge keys exist and are unique,
    so a bad response fails here instead of halfway through a MERGE."""
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if not header:
        raise ValueError("ECB response has no header row")
    missing = [k for k in MERGE_KEYS if k not in header]
    if missing:
        raise ValueError(f"ECB CSV is missing merge key column(s): {', '.join(missing)}")

    key_idx = [header.index(k) for k in MERGE_KEYS]
    seen = set()
    for n, row in enumerate(reader, start=2):
        if not row:
            continue  # blank line
        if len(row) != len(header):
            raise ValueError(f"ECB CSV line {n} has {len(row)} fields, header has {len(header)}")
        key = tuple(row[i] for i in key_idx)
        if key in seen:
            raise ValueError(f"Duplicate {MERGE_KEYS} in ECB response: {key}")
        seen.add(key)
    return header, len(seen)


def upload_to_gcs(table, text, file_name, bucket, load_date):
    path = f"fx/{table}/load_date={load_date}/{file_name}"
    gcs_uri = f"gs://{bucket.name}/{path}"
    bucket.blob(path).upload_from_string(text, content_type="text/csv")
    return gcs_uri


def table_exists(bq_client, table_id):
    try:
        bq_client.get_table(table_id)
        return True
    except NotFound:
        return False


def max_time_period(bq_client, table_id):
    """MAX(TIME_PERIOD) of the (existing) final table as a date, or None if it has no rows.

    TIME_PERIOD is a STRING of ISO dates, so MAX sorts correctly; a malformed value
    makes fromisoformat raise, which fails the run loudly instead of guessing a date.
    """
    rows = list(bq_client.query(f"SELECT MAX(TIME_PERIOD) AS latest FROM `{table_id}`").result())
    latest = rows[0]["latest"] if rows else None
    return datetime.date.fromisoformat(latest) if latest else None


def build_merge_sql(table_id, tmp_id, header):
    cols = header + ["_loaded_at", "_source_uri"]
    q = lambda c: f"`{c}`"
    on = " AND ".join(f"T.{q(k)} = S.{q(k)}" for k in MERGE_KEYS)
    updates = ",\n            ".join(f"{q(c)} = S.{q(c)}" for c in cols if c not in MERGE_KEYS)
    insert_cols = ", ".join(q(c) for c in cols)
    insert_vals = ", ".join(f"S.{q(c)}" for c in cols)
    return f"""
        MERGE `{table_id}` T
        USING (
            SELECT
                *,
                CURRENT_TIMESTAMP() AS _loaded_at,
                @source_uri AS _source_uri
            FROM `{tmp_id}`
        ) S
        ON {on}
        WHEN MATCHED THEN UPDATE SET
            {updates}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
    """


def load_to_bigquery(bq_client, dataset, table, gcs_uri, header, source_rows):
    table_id, tmp_id = table_ids(bq_client, dataset, table)

    schema = [bigquery.SchemaField(col, "STRING") for col in header]

    load_job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
        encoding="UTF-8",
    )

    exists = table_exists(bq_client, table_id)

    if exists:
        query = build_merge_sql(table_id, tmp_id, header)
    else:
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
        validate_row_count(table, source_rows, load_job.output_rows)

        # 3. temp table -> final table (first run: create/replace, later runs: merge)
        bq_client.query(query, job_config=query_config).result()

        print(f"{'Merged' if exists else 'Created'} {load_job.output_rows} rows in {table_id}")
        return load_job.output_rows, table_id, source_rows

    finally:
        # 4. clean up temp table
        bq_client.delete_table(tmp_id, not_found_ok=True)


def fetch_ecb_rates(currencies, start_date, end_date, url_template=URL_TEMPLATE):
    """Return ECB daily rates as CSV text, or None if the window has no data.

    "Nothing" and "error" must never look the same:
      200            -> CSV text (None if the body is empty)
      204 / 404      -> no data in this window, BUT every requested currency that
                        is missing from the result is probed on its own; if the ECB
                        doesn't know it at all -> ValueError (typo), not None
      429 / 5xx      -> retry (Retry-After seconds if given, else exponential
                        backoff), up to MAX_ATTEMPTS, then raise
      timeout / connection lost -> retried like a 5xx
      other 4xx      -> raise now, with the response body in the message

    Every request, including the currency probes, goes through the same retry
    logic. url_template has a {key} placeholder (e.g. "USD+GBP"); pointing it at
    another server (a local stub, httpbin.org/status/429, ...) makes this testable.
    """

    def get(key, params):
        """GET with retries. Returns the response for 200 / 204 / 404, raises otherwise."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            resp = None
            try:
                resp = requests.get(url_template.format(key=key), params=params, timeout=TIMEOUT)
            except (requests.Timeout, requests.ConnectionError) as exc:
                problem, error = type(exc).__name__, exc
            else:
                code = resp.status_code
                if code in (200, 204, 404):
                    return resp
                if code != 429 and not 500 <= code < 600:
                    raise requests.HTTPError(f"HTTP {code}: {resp.text[:500]}", response=resp)
                problem = f"HTTP {code}"
                error = requests.HTTPError(
                    f"HTTP {code} after {attempt} attempts: {resp.text[:500]}", response=resp
                )

            if attempt == MAX_ATTEMPTS:
                raise error
            wait = resp.headers.get("Retry-After", "") if resp is not None else ""
            delay = int(wait) if wait.isdigit() else 2 ** (attempt - 1) + random.random()
            delay = min(delay, MAX_DELAY)
            print(f"[{key}] attempt {attempt}/{MAX_ATTEMPTS} failed ({problem}); waiting {delay:.1f}s")
            time.sleep(delay)

    resp = get(
        "+".join(currencies),
        {"format": "csvdata", "startPeriod": start_date, "endPeriod": end_date},
    )
    # requests assumes ISO-8859-1 for text/* without a charset; BigQuery load says UTF-8
    resp.encoding = "utf-8"
    text = resp.text if resp.status_code == 200 and resp.text.strip() else None

    present = set()
    if text:
        reader = csv.DictReader(io.StringIO(text))
        if "CURRENCY" not in (reader.fieldnames or []):
            raise ValueError(f"Unexpected CSV header from ECB: {text[:200]!r}")
        present = {row["CURRENCY"] for row in reader}

    # Empty window or partial result: is each missing currency real?
    for ccy in sorted(set(currencies) - present):
        probe = get(ccy, {"format": "csvdata", "lastNObservations": 1})
        if probe.status_code != 200:
            raise ValueError(
                f"Unknown currency code {ccy!r} (ECB said {probe.status_code}: {probe.text[:200]!r})"
            )

    return text


def main():
    config = load_config()
    today = datetime.date.today()
    load_date = today.isoformat()
    dataset = config["bigquery_dataset"]
    storage_client = storage.Client(project=config["project_id"])
    bucket = storage_client.bucket(config["bucket_name"])
    bq_client = bigquery.Client(project=config["project_id"])

    log_table_id = ensure_log_table(bq_client, dataset)
    run_id = uuid.uuid4().hex
    started_at = datetime.datetime.now(datetime.timezone.utc)
    gcs_uri = None
    log_event(bq_client, log_table_id, run_id, TABLE, "started", started_at, source=SOURCE)

    try:
        final_id, _ = table_ids(bq_client, dataset, TABLE)
        first_run = not table_exists(bq_client, final_id)
        if config["use_default_start_date"]:
            start_date = DEFAULT_START_DATE
        else:
            latest = None if first_run else max_time_period(bq_client, final_id)
            if latest is None:
                print(
                    f"{final_id} has nothing loaded yet (no table or no rows), so there is no "
                    f"MAX(TIME_PERIOD) to anchor on; using DEFAULT_START_DATE {DEFAULT_START_DATE}"
                )
                start_date = DEFAULT_START_DATE
            else:
                start_date = (latest - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
        end_date = load_date

        text = fetch_ecb_rates(config["fx_currencies"], start_date, end_date)

        if text is None:
            if first_run:
                raise ValueError(
                    f"ECB returned no data for {start_date} -> {end_date} on the first load; "
                    "refusing to create an empty table"
                )
            print(f"{TABLE}: no data from ECB for {start_date} -> {end_date}, nothing to load")
            log_event(bq_client, log_table_id, run_id, TABLE, "success", started_at,
                      source=SOURCE, source_rows=0, loaded_rows=0)
            return

        header, source_rows = parse_ecb_csv(text)
        file_name = f"ecb_exr_{start_date}_{end_date}.csv"
        gcs_uri = upload_to_gcs(TABLE, text, file_name, bucket, load_date)
        rows, table_id, source_rows = load_to_bigquery(
            bq_client, dataset, TABLE, gcs_uri, header, source_rows
        )
        log_event(bq_client, log_table_id, run_id, TABLE, "success", started_at,
                  source=SOURCE, gcs_uri=gcs_uri, source_rows=source_rows, loaded_rows=rows)
        print("1 succeeded, 0 failed")
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        print(f"FAILED {TABLE}: {error}")
        log_event(bq_client, log_table_id, run_id, TABLE, "failed", started_at,
                  source=SOURCE, gcs_uri=gcs_uri, error=error)
        sys.exit(1)


if __name__ == "__main__":
    main()