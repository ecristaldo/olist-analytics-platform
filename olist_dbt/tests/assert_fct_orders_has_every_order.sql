-- One row per order in the staging table, no more and no less. A join that drops orders
-- (an inner join by mistake) or multiplies them changes the count. Returns a row, which
-- makes dbt fail the test, when the counts differ.

with fct as (

    select count(*) as n from {{ ref('fct_orders') }}

),

stg as (

    select count(*) as n from {{ ref('stg_olist__orders') }}

)

select
    'fct_orders row count differs from stg_olist__orders' as problem,
    fct.n as fct_rows,
    stg.n as stg_rows
from fct
cross join stg
where fct.n != stg.n
