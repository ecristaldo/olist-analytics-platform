# ##GCS
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

# ##FX
1- Going for ECB, more complext but has more information and don't require me to connect to third-party. The ECB reference rates are published once per TARGET working day at 16:00 CET.
2- I can send a APi request to ECB for BRL and GBP with this key (+ sign to inlcude more currencies if needed) : D.BRL+GBP.EUR.SP00.A
(Daily, BRL observed, EUR base, reference rates, standard series)
The calculation will happen in dbt. Raw will have no calculation.
3- I can query the API by using this key: startPeriod=[START_DATE]&endPeriod=[LATEST_DATE]; the date I can get by finding the min date from olist_orders.order_purchased_timestamp in BQ and set a variable START_DATE = MIN - 7 days.
I can create a full daily calendar (including weekends), LEFT-JOIN ECB rates, Forward-Fill accross weekends/holidays. Optinally I can add a flag is_forward_filled = true/false and last_ecb_date = date of the actual ECB observation used. This also would help creating the LATEST_DATE variable if happens to be a weekend or holiday.
4- I would land in GSC in CSV, ECB provide that option by using the key **format=csvdata** and send everything to BQ.
5- 429 can be dealt by checking the header "Retry-After", this might tell how long I should wait.
In case returns None, I can use the **Exponential backoff** by using a formula like: "delay = min(base * (2 ** attempt) + random.uniform(0, base), max_delay)".
Also have a max attempts set to 5.
for 500 (internal server error) I can retry with backoff system for that.
Another thing to keep in mind is to use timeout= to requests.get to prevent the script to wait forever in case a sever never answers.

# ##Query generated
```
MERGE `olist-analytics-eduardo.raw.ecb_fx_rates` T
        USING (
            SELECT
                *,
                CURRENT_TIMESTAMP() AS _loaded_at,
                @source_uri AS _source_uri
            FROM `olist-analytics-eduardo.raw._tmp_ecb_fx_rates`
        ) S
        ON T.`KEY` = S.`KEY` AND T.`TIME_PERIOD` = S.`TIME_PERIOD`
        WHEN MATCHED THEN UPDATE SET
            `FREQ` = S.`FREQ`,
            `CURRENCY` = S.`CURRENCY`,
            `CURRENCY_DENOM` = S.`CURRENCY_DENOM`,
            `EXR_TYPE` = S.`EXR_TYPE`,
            `EXR_SUFFIX` = S.`EXR_SUFFIX`,
            `OBS_VALUE` = S.`OBS_VALUE`,
            `OBS_STATUS` = S.`OBS_STATUS`,
            `OBS_CONF` = S.`OBS_CONF`,
            `OBS_PRE_BREAK` = S.`OBS_PRE_BREAK`,
            `OBS_COM` = S.`OBS_COM`,
            `TIME_FORMAT` = S.`TIME_FORMAT`,
            `BREAKS` = S.`BREAKS`,
            `COLLECTION` = S.`COLLECTION`,
            `COMPILING_ORG` = S.`COMPILING_ORG`,
            `DISS_ORG` = S.`DISS_ORG`,
            `DOM_SER_IDS` = S.`DOM_SER_IDS`,
            `PUBL_ECB` = S.`PUBL_ECB`,
            `PUBL_MU` = S.`PUBL_MU`,
            `PUBL_PUBLIC` = S.`PUBL_PUBLIC`,
            `UNIT_INDEX_BASE` = S.`UNIT_INDEX_BASE`,
            `COMPILATION` = S.`COMPILATION`,
            `COVERAGE` = S.`COVERAGE`,
            `DECIMALS` = S.`DECIMALS`,
            `NAT_TITLE` = S.`NAT_TITLE`,
            `SOURCE_AGENCY` = S.`SOURCE_AGENCY`,
            `SOURCE_PUB` = S.`SOURCE_PUB`,
            `TITLE` = S.`TITLE`,
            `TITLE_COMPL` = S.`TITLE_COMPL`,
            `UNIT` = S.`UNIT`,
            `UNIT_MULT` = S.`UNIT_MULT`,
            `_loaded_at` = S.`_loaded_at`,
            `_source_uri` = S.`_source_uri`
        WHEN NOT MATCHED THEN INSERT (`KEY`, `FREQ`, `CURRENCY`, `CURRENCY_DENOM`, `EXR_TYPE`, `EXR_SUFFIX`, `TIME_PERIOD`, `OBS_VALUE`, `OBS_STATUS`, `OBS_CONF`, `OBS_PRE_BREAK`, `OBS_COM`, `TIME_FORMAT`, `BREAKS`, `COLLECTION`, `COMPILING_ORG`, `DISS_ORG`, `DOM_SER_IDS`, `PUBL_ECB`, `PUBL_MU`, `PUBL_PUBLIC`, `UNIT_INDEX_BASE`, `COMPILATION`, `COVERAGE`, `DECIMALS`, `NAT_TITLE`, `SOURCE_AGENCY`, `SOURCE_PUB`, `TITLE`, `TITLE_COMPL`, `UNIT`, `UNIT_MULT`, `_loaded_at`, `_source_uri`) VALUES (S.`KEY`, S.`FREQ`, S.`CURRENCY`, S.`CURRENCY_DENOM`, S.`EXR_TYPE`, S.`EXR_SUFFIX`, S.`TIME_PERIOD`, S.`OBS_VALUE`, S.`OBS_STATUS`, S.`OBS_CONF`, S.`OBS_PRE_BREAK`, S.`OBS_COM`, S.`TIME_FORMAT`, S.`BREAKS`, S.`COLLECTION`, S.`COMPILING_ORG`, S.`DISS_ORG`, S.`DOM_SER_IDS`, S.`PUBL_ECB`, S.`PUBL_MU`, S.`PUBL_PUBLIC`, S.`UNIT_INDEX_BASE`, S.`COMPILATION`, S.`COVERAGE`, S.`DECIMALS`, S.`NAT_TITLE`, S.`SOURCE_AGENCY`, S.`SOURCE_PUB`, S.`TITLE`, S.`TITLE_COMPL`, S.`UNIT`, S.`UNIT_MULT`, S.`_loaded_at`, S.`_source_uri`)

```