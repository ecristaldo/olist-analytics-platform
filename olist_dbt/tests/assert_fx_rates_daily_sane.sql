-- Returns a row for every problem found; dbt fails the test if any row comes back.
-- It also fails when 2018 is missing altogether, so "no data" can't pass as "all fine".

with fx as (

    select * from {{ ref('int_fx__rates_daily') }}

),

fx_2018 as (

    select * from fx
    where rate_date between date '2018-01-01' and date '2018-12-31'

)

-- 1. every calendar day of 2018 is there, weekends included
select
    'expected 365 rows for 2018' as problem,
    cast(null as date) as rate_date,
    cast(count(*) as numeric) as value
from fx_2018
having count(*) != 365

union all

-- 2. 1 BRL was roughly 0.20 GBP in 2018 (a value near 5 means the division is upside down)
select
    'gbp_per_brl outside 0.15-0.30 in 2018',
    rate_date,
    gbp_per_brl
from fx_2018
where gbp_per_brl is null
   or gbp_per_brl not between 0.15 and 0.30

union all

-- 3. a weekend is never a real ECB day
select
    'weekend not forward-filled',
    rate_date,
    gbp_per_brl
from fx
where format_date('%A', rate_date) in ('Saturday', 'Sunday')
  and (not is_forward_filled or last_ecb_date >= rate_date)

union all

-- 4. forward-filling should only bridge weekends and holidays (4 days at the longest,
--    e.g. Easter Thursday -> Tuesday); older than that means ECB data is missing
select
    'rate older than 5 days',
    rate_date,
    gbp_per_brl
from fx
where date_diff(rate_date, last_ecb_date, day) > 5
