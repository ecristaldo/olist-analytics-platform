-- Total gross revenue in fct_orders must equal items + freight summed straight from the RAW
-- table, not from staging: a bug in staging (a wrong cast, a filter, a join) would otherwise
-- be in both numbers and pass unnoticed. Returns a row, which fails the test, when the two
-- totals differ by more than one cent.

with fct as (

    select coalesce(sum(gross_revenue_brl), 0) as fct_total
    from {{ ref('fct_orders') }}

),

raw as (

    select coalesce(sum(cast(price as numeric) + cast(freight_value as numeric)), 0) as raw_total
    from {{ source('olist', 'olist_order_items') }}

)

select
    fct.fct_total,
    raw.raw_total,
    fct.fct_total - raw.raw_total as difference
from fct
cross join raw
where abs(fct.fct_total - raw.raw_total) > 0.01
