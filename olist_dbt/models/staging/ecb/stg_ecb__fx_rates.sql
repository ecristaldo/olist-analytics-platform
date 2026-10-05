with source as (

    select * from {{ source('ecb', 'ecb_fx_rates') }}

),

renamed as (

    select
        CURRENCY as currency,
        cast(TIME_PERIOD as date) as rate_date,
        cast(OBS_VALUE as numeric) as rate_per_eur,
        OBS_STATUS as obs_status,
        _loaded_at

    from source
)

select * from renamed