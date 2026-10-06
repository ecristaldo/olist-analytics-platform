-- One row per calendar day (weekends and holidays included) with the GBP-per-BRL
-- cross rate, forward-filled from the last day the ECB actually published.
--
-- The ECB quotes "units of currency per 1 EUR" (rate_per_eur):
--   GBP 0.88  ->  1 EUR = 0.88 GBP
--   BRL 4.30  ->  1 EUR = 4.30 BRL
-- so 1 BRL = (GBP per EUR) / (BRL per EUR) = 0.88 / 4.30 = ~0.205 GBP.
-- If this comes out near 5 instead of 0.2, the division is upside down.

with ecb_rates as (

    select
        rate_date,
        currency,
        rate_per_eur
    from {{ ref('stg_ecb__fx_rates') }}
    where currency in ('GBP', 'BRL')

),

-- one row per ECB publication day, GBP and BRL side by side
pivoted as (

    select
        rate_date as ecb_date,
        max(if(currency = 'GBP', rate_per_eur, null)) as gbp_per_eur,
        max(if(currency = 'BRL', rate_per_eur, null)) as brl_per_eur
    from ecb_rates
    group by rate_date

),

-- the cross rate, only on days where both currencies were published, so every
-- rate comes from one real pair (a day with just one of them counts as a gap)
ecb_days as (

    select
        ecb_date,
        gbp_per_eur / brl_per_eur as gbp_per_brl
    from pivoted
    where gbp_per_eur is not null
      and brl_per_eur is not null

),

bounds as (

    select
        min(ecb_date) as first_date,
        max(ecb_date) as last_date
    from ecb_days

),

-- every calendar day between the first and the last real observation
calendar as (

    select rate_date
    from bounds,
        unnest(generate_date_array(bounds.first_date, bounds.last_date)) as rate_date

),

-- NULLs on weekends and holidays
joined as (

    select
        calendar.rate_date,
        ecb_days.ecb_date,
        ecb_days.gbp_per_brl
    from calendar
    left join ecb_days
        on ecb_days.ecb_date = calendar.rate_date

),

-- forward fill: carry the last non-NULL value down to the following days
filled as (

    select
        rate_date,
        last_value(gbp_per_brl ignore nulls) over w as gbp_per_brl,
        last_value(ecb_date ignore nulls) over w as last_ecb_date
    from joined
    window w as (
        order by rate_date
        rows between unbounded preceding and current row
    )

)

select
    rate_date,
    gbp_per_brl,
    last_ecb_date,
    last_ecb_date != rate_date as is_forward_filled
from filled
